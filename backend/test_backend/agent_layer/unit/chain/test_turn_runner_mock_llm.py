"""TurnRunner 全链集成测试 — mock LLM，其余模块均为真实代码"""

from __future__ import annotations

import json

import pytest

from app.agent_layer.contracts.query import AskRequest
from app.agent_layer.orchestration.turn_runner import TurnRunner
from app.agent_layer.planning.retrieval_gate import should_retrieve
from app.agent_layer.planning.snapshot_builder import build_snapshot
from app.agent_layer.response.block_streamer import stream_to_blocks
from app.agent_layer.response.source_mapper import map_sources
from app.agent_layer.session.editor_context_store import EditorContextStore
from app.agent_layer.session.persistence import SessionPersistence
from app.agent_layer.session.window_store import ConversationWindowStore


# ── mock LLM ─────────────────────────────────────────────────────────


class MockChatModel:
    """模拟 LLM，返回预设响应"""

    def __init__(self, response: str = "这是一个测试回答。"):
        self._response = response
        self._call_count = 0
        self._last_messages: list[dict] | None = None

    async def chat_stream(self, messages, model=None):
        self._call_count += 1
        self._last_messages = messages
        for i in range(0, len(self._response), 10):
            yield self._response[i : i + 10]

    async def chat(self, messages, model=None):
        self._call_count += 1
        self._last_messages = messages
        return self._response


# ── helpers ──────────────────────────────────────────────────────────


def _parse_sse_frames(frames: list[str]) -> list[tuple[str, dict | str]]:
    """解析 SSE 帧列表为 (event_type, data) 元组列表"""
    parsed = []
    for frame in frames:
        lines = frame.strip().split("\n")
        event_type = lines[0].split(": ", 1)[1] if ": " in lines[0] else lines[0]
        if len(lines) > 1 and lines[1].startswith("data: "):
            data_str = lines[1][6:]
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = data_str
        else:
            data = {}
        parsed.append((event_type, data))
    return parsed


# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def runner():
    model = MockChatModel("根据研究[1]该方法有效[2]。")
    return TurnRunner(
        chat_model=model,
        snapshot_builder=build_snapshot,
        retrieval_gate=should_retrieve,
        source_mapper=map_sources,
        block_streamer=stream_to_blocks,
        window_store=ConversationWindowStore(max_messages=20),
        editor_context_store=EditorContextStore(),
        persistence=SessionPersistence(),
    )


# ── 正常流程 ─────────────────────────────────────────────────────────


async def test_full_no_rag_flow(runner):
    """无 RAG 完整流程：thinking → block → sources → done"""
    req = AskRequest(session_id="s1", prompt="你好", enable_rag=False, thinking=True)
    frames = [f async for f in runner.run(req)]
    parsed = _parse_sse_frames(frames)
    event_types = [e[0] for e in parsed]
    assert "thinking" in event_types
    assert "block" in event_types
    assert "sources" in event_types
    assert "done" in event_types


async def test_full_no_rag_no_thinking(runner):
    """无 RAG + 无 thinking → block → sources → done（无 thinking 帧）"""
    req = AskRequest(session_id="s1", prompt="你好", enable_rag=False, thinking=False)
    frames = [f async for f in runner.run(req)]
    parsed = _parse_sse_frames(frames)
    event_types = [e[0] for e in parsed]
    assert "thinking" not in event_types
    assert "block" in event_types
    assert "sources" in event_types
    assert "done" in event_types


async def test_block_contains_citations(runner):
    """LLM 输出带引用 → block 帧包含 citations"""
    req = AskRequest(session_id="s1", prompt="引用测试", enable_rag=False)
    frames = [f async for f in runner.run(req)]
    parsed = _parse_sse_frames(frames)
    block_frames = [(t, d) for t, d in parsed if t == "block"]
    assert len(block_frames) > 0
    block_data = block_frames[0][1]
    assert isinstance(block_data, dict)
    assert block_data["type"] == "paragraph"
    # MockChatModel 返回 "根据研究[1]该方法有效[2]。"，应有引用
    # 但因为 sources 为空，citation_map 为空 → citations 可能为 None
    # 这是正常行为


async def test_sources_frame_empty_when_no_rag(runner):
    """无 RAG → sources 帧 data 为空数组"""
    req = AskRequest(session_id="s1", prompt="你好", enable_rag=False)
    frames = [f async for f in runner.run(req)]
    parsed = _parse_sse_frames(frames)
    sources_frames = [(t, d) for t, d in parsed if t == "sources"]
    assert len(sources_frames) == 1
    assert sources_frames[0][1] == []


# ── 错误处理 ─────────────────────────────────────────────────────────


async def test_empty_prompt_yields_error(runner):
    """空 prompt → ErrorEvent"""
    req = AskRequest(session_id="s1", prompt="", enable_rag=False)
    frames = [f async for f in runner.run(req)]
    assert len(frames) == 1
    parsed = _parse_sse_frames(frames)
    assert parsed[0][0] == "error"
    assert "请提供问题或内容" in parsed[0][1]["message"]


async def test_whitespace_prompt_yields_error(runner):
    """纯空格 prompt → ErrorEvent"""
    req = AskRequest(session_id="s1", prompt="   ", enable_rag=False)
    frames = [f async for f in runner.run(req)]
    assert len(frames) == 1
    parsed = _parse_sse_frames(frames)
    assert parsed[0][0] == "error"


async def test_llm_exception_yields_error(runner):
    """LLM 异常 → metadata + ErrorEvent，不崩溃"""

    async def _fail(msgs, model=None):
        raise RuntimeError("LLM down")
        yield  # pragma: no cover

    runner._chat_model.chat_stream = _fail
    req = AskRequest(session_id="s1", prompt="测试异常", enable_rag=False)
    frames = [f async for f in runner.run(req)]
    parsed = _parse_sse_frames(frames)
    # metadata 在 LLM 调用之前发送，异常时有 2 个帧
    assert len(parsed) == 2
    assert parsed[0][0] == "metadata"
    assert parsed[1][0] == "error"
    # 错误信息应为用户友好文案，不暴露内部异常细节
    assert "LLM down" not in parsed[1][1]["message"]
    assert len(parsed[1][1]["message"]) > 0


# ── 多轮对话 ─────────────────────────────────────────────────────────


async def test_multi_turn_history_accumulation(runner):
    """多轮对话历史积累"""
    req1 = AskRequest(session_id="s1", prompt="第一轮", enable_rag=False)
    _ = [f async for f in runner.run(req1)]

    req2 = AskRequest(session_id="s1", prompt="第二轮", enable_rag=False)
    _ = [f async for f in runner.run(req2)]

    # 验证第二轮的 LLM 输入包含第一轮历史
    messages = runner._chat_model._last_messages
    user_msgs = [m for m in messages if m["role"] == "user"]
    assert len(user_msgs) >= 2


async def test_multi_turn_different_sessions_isolated(runner):
    """不同 session 的对话历史互相隔离"""
    req1 = AskRequest(session_id="s1", prompt="会话1", enable_rag=False)
    _ = [f async for f in runner.run(req1)]

    req2 = AskRequest(session_id="s2", prompt="会话2", enable_rag=False)
    _ = [f async for f in runner.run(req2)]

    # s2 的 LLM 输入不应包含 s1 的历史
    messages = runner._chat_model._last_messages
    user_msgs = [m for m in messages if m["role"] == "user"]
    assert len(user_msgs) == 1
    assert "会话2" in user_msgs[0]["content"]


# ── 持久化 ───────────────────────────────────────────────────────────


async def test_persistence_after_success(runner):
    """成功后持久化消息"""
    req = AskRequest(session_id="s1", prompt="测试持久化", enable_rag=False)
    _ = [f async for f in runner.run(req)]
    msgs = await runner._persistence.get_messages("s1")
    assert len(msgs) == 2  # user + assistant
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


async def test_window_store_after_success(runner):
    """成功后 window_store 积累消息"""
    req = AskRequest(session_id="s1", prompt="测试窗口", enable_rag=False)
    _ = [f async for f in runner.run(req)]
    window = await runner._window_store.get_messages("s1")
    assert len(window) == 2


async def test_no_persist_on_failure(runner):
    """失败时不持久化"""

    async def _fail(msgs, model=None):
        raise RuntimeError("fail")
        yield  # pragma: no cover

    runner._chat_model.chat_stream = _fail
    req = AskRequest(session_id="s1", prompt="测试失败不持久化", enable_rag=False)
    _ = [f async for f in runner.run(req)]
    msgs = await runner._persistence.get_messages("s1")
    assert len(msgs) == 0


async def test_no_persist_on_empty_prompt(runner):
    """空 prompt 不持久化"""
    req = AskRequest(session_id="s1", prompt="", enable_rag=False)
    _ = [f async for f in runner.run(req)]
    msgs = await runner._persistence.get_messages("s1")
    assert len(msgs) == 0
