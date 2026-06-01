"""安全对抗测试：prompt injection、source-content injection、会话泄露、错误脱敏"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import APIConnectionError, APIStatusError, RateLimitError

from app.agent_layer.contracts.query import AskRequest
from app.agent_layer.orchestration.turn_runner import TurnRunner, _user_friendly_error
from app.agent_layer.planning.snapshot_builder import build_snapshot
from app.agent_layer.planning.retrieval_gate import should_retrieve
from app.agent_layer.response.source_mapper import map_sources
from app.agent_layer.response.block_streamer import stream_to_blocks
from app.agent_layer.runtime.chat_model import ChatModel
from app.agent_layer.session.window_store import ConversationWindowStore
from app.agent_layer.session.editor_context_store import EditorContextStore
from app.agent_layer.session.persistence import SessionPersistence


# ──────────────────────────────────────────────
# 错误脱敏：确定性验证每个异常分支
# ──────────────────────────────────────────────
class TestErrorSanitization:
    def test_rate_limit_sanitized(self):
        mock_resp = MagicMock()
        mock_resp.headers = {}
        exc = RateLimitError(message="rate limited", response=mock_resp, body={})
        msg = _user_friendly_error(exc)
        assert "rate limited" not in msg
        assert "请稍后" in msg

    def test_connection_error_sanitized(self):
        mock_req = MagicMock()
        exc = APIConnectionError(request=mock_req)
        msg = _user_friendly_error(exc)
        assert "APIConnectionError" not in msg
        assert "无法连接" in msg

    def test_server_error_sanitized(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.headers = {}
        mock_resp.json.return_value = {"error": {"message": "internal"}}
        exc = APIStatusError(message="internal error", response=mock_resp, body={})
        msg = _user_friendly_error(exc)
        assert "internal" not in msg
        assert "暂时不可用" in msg

    def test_client_error_sanitized(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.headers = {}
        mock_resp.json.return_value = {"error": {"message": "forbidden"}}
        exc = APIStatusError(message="forbidden", response=mock_resp, body={})
        msg = _user_friendly_error(exc)
        assert "forbidden" not in msg
        assert "403" in msg

    def test_timeout_sanitized(self):
        exc = TimeoutError("connection timed out")
        msg = _user_friendly_error(exc)
        assert "timed out" not in msg
        assert "超时" in msg

    def test_generic_error_sanitized(self):
        exc = RuntimeError("/app/secret_module.py line 42 secret_function() failed")
        msg = _user_friendly_error(exc)
        assert "/app/" not in msg
        assert ".py" not in msg
        assert "secret" not in msg

    def test_no_traceback_in_output(self):
        """所有异常类型都不应包含 Traceback 或文件路径"""
        errors = [
            RuntimeError("Traceback (most recent call last): ..."),
            ValueError("File \"/app/config.py\", line 10"),
            Exception("openai.APIError: something"),
        ]
        for exc in errors:
            msg = _user_friendly_error(exc)
            assert "Traceback" not in msg
            assert ".py" not in msg
            assert "openai" not in msg.lower()


# ──────────────────────────────────────────────
# 会话隔离：不同 session 互不干扰
# ──────────────────────────────────────────────
class TestSessionIsolation:
    @pytest.mark.asyncio
    async def test_sessions_dont_leak(self):
        """session A 的历史不出现在 session B 的消息中"""
        ws = ConversationWindowStore(max_messages=20)
        await ws.add_message("session-a", {"role": "user", "content": "A的秘密"})
        await ws.add_message("session-a", {"role": "assistant", "content": "A的回复"})

        b_msgs = await ws.get_messages("session-b")
        assert len(b_msgs) == 0

        a_msgs = await ws.get_messages("session-a")
        assert len(a_msgs) == 2
        assert "A的秘密" in a_msgs[0]["content"]

    @pytest.mark.asyncio
    async def test_persistence_isolation(self):
        """persistence 中不同 session 的消息独立"""
        p = SessionPersistence()
        await p.save_message("s1", "user", "session 1 content")
        await p.save_message("s2", "user", "session 2 content")

        s1 = await p.get_messages("s1")
        s2 = await p.get_messages("s2")
        assert len(s1) == 1
        assert len(s2) == 1
        assert s1[0]["content"] == "session 1 content"
        assert s2[0]["content"] == "session 2 content"


# ──────────────────────────────────────────────
# 持久化降级：存储失败不影响 SSE 输出
# ──────────────────────────────────────────────
class TestPersistenceDegradation:
    @pytest.mark.asyncio
    async def test_window_store_failure_doesnt_break_sse(self):
        """window_store 抛异常时 SSE 流仍正常完成"""
        mock_model = AsyncMock(spec=ChatModel)

        async def fake_stream(msgs, model=None):
            yield "回复内容"

        mock_model.chat_stream = fake_stream

        ws = ConversationWindowStore(max_messages=20)
        # monkey-patch 让 add_message 抛异常
        original_add = ws.add_message

        async def broken_add(*args, **kwargs):
            raise RuntimeError("storage full")

        ws.add_message = broken_add

        runner = TurnRunner(
            chat_model=mock_model,
            snapshot_builder=build_snapshot,
            retrieval_gate=should_retrieve,
            source_mapper=map_sources,
            block_streamer=stream_to_blocks,
            window_store=ws,
            editor_context_store=EditorContextStore(),
            persistence=SessionPersistence(),
        )

        req = AskRequest(session_id="degrade-test", prompt="测试降级", enable_rag=False)
        frames = []
        async for frame in runner.run(req):
            frames.append(frame)

        event_types = []
        for f in frames:
            if "event: " in f:
                event_types.append(f.split("event: ")[1].split("\n")[0])

        assert "done" in event_types, "SSE 流应正常完成（done 事件）"
        assert "error" not in event_types, "持久化失败不应产生 error 事件"


# ──────────────────────────────────────────────
# 输入边界：超长输入、特殊字符
# ──────────────────────────────────────────────
class TestInputBoundaries:
    def test_very_long_prompt_snapshot(self):
        """超长 prompt 不应在快照构建时崩溃"""
        long_prompt = "A" * 50000
        req = AskRequest(session_id="s1", prompt=long_prompt, enable_rag=False)
        snapshot = build_snapshot(request=req, editor_context=None, recent_window=[], history_summary="")
        assert snapshot.prompt == long_prompt

    def test_special_chars_in_prompt(self):
        """特殊字符不应导致快照构建失败"""
        special = "<script>alert('xss')</script>\\n\\r\\t`'\"${}"
        req = AskRequest(session_id="s1", prompt=special, enable_rag=False)
        snapshot = build_snapshot(request=req, editor_context=None, recent_window=[], history_summary="")
        assert snapshot.prompt == special

    def test_empty_selection_and_draft(self):
        """selection 和 draft 为空时快照字段为空字符串"""
        req = AskRequest(session_id="s1", prompt="hi", enable_rag=False)
        snapshot = build_snapshot(request=req, editor_context=None, recent_window=[], history_summary="")
        assert snapshot.selection == ""
        assert snapshot.written_context == ""
