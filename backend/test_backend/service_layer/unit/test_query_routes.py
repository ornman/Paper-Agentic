"""query_routes 单元测试"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _build_app(*, has_editor_store=True, has_window_store=True, turn_runner=None):
    """构造带内存态 container 的 FastAPI app"""
    from app.service_layer.api.query_routes import router
    from app.agent_layer.session.editor_context_store import EditorContextStore
    from app.agent_layer.session.persistence import SessionPersistence
    from app.agent_layer.session.window_store import ConversationWindowStore

    app = FastAPI()
    app.include_router(router)

    container = SimpleNamespace(
        chat_model=MagicMock(),
        vector_store=MagicMock(),
        keyword_search=MagicMock(),
        embedding_client=MagicMock(),
        conversation_window=ConversationWindowStore(max_messages=20) if has_window_store else None,
        editor_context_store=EditorContextStore() if has_editor_store else None,
        session_persistence=SessionPersistence(),
        settings=SimpleNamespace(context_window_tokens=32000, max_output_tokens=4096),
        reflection_chat_model=MagicMock(),
    )
    container.chat_model.max_context_tokens = 32000
    if turn_runner is not None:
        container.turn_runner = turn_runner

    app.state.container = container
    return app, container


class TestQueryMetadataEvent:
    """验证首个 SSE 帧是 metadata 事件"""

    def test_first_frame_is_metadata(self):
        app, container = _build_app()
        client = TestClient(app)

        mock_runner = MagicMock()

        async def fake_run(request):
            yield 'event: metadata\ndata: {"request_id":"r1","session_id":"s1","used_inputs":{"prompt":1.0,"selection":0.0,"written_context":0.0,"rag_evidence":0.0},"context_tokens":10,"remaining_tokens":31990,"remaining_ratio":0.9997,"retrieval_planned":true,"degraded_flags":[],"cache_mode":"memory"}\n\n'
            yield 'event: done\ndata: {}\n\n'

        mock_runner.run = fake_run

        with patch("app.service_layer.api.query_routes._build_runner", return_value=mock_runner):
            resp = client.post(
                "/query",
                json={"session_id": "s1", "prompt": "hello"},
                headers={"Accept": "text/event-stream"},
            )

        assert resp.status_code == 200
        lines = resp.text.strip().split("\n")
        # 找到第一个 event 行
        first_event = None
        for line in lines:
            if line.startswith("event:"):
                first_event = line.split(":", 1)[1].strip()
                break
        assert first_event == "metadata"

    def test_metadata_contains_required_fields(self):
        app, container = _build_app()
        client = TestClient(app)

        mock_runner = MagicMock()

        async def fake_run(request):
            yield 'event: metadata\ndata: {"request_id":"r1","session_id":"s1","used_inputs":{"prompt":1.0},"context_tokens":10,"remaining_tokens":31990,"remaining_ratio":0.9997,"retrieval_planned":true,"degraded_flags":[],"cache_mode":"memory"}\n\n'
            yield 'event: done\ndata: {}\n\n'

        mock_runner.run = fake_run

        with patch("app.service_layer.api.query_routes._build_runner", return_value=mock_runner):
            resp = client.post(
                "/query",
                json={"session_id": "s1", "prompt": "hello"},
            )

        assert resp.status_code == 200
        # 解析 metadata data
        for line in resp.text.split("\n"):
            if line.startswith("data:") and '"request_id"' in line:
                data = json.loads(line[5:].strip())
                assert "request_id" in data
                assert "session_id" in data
                assert "used_inputs" in data
                assert "context_tokens" in data
                assert "remaining_tokens" in data
                assert "remaining_ratio" in data
                assert "retrieval_planned" in data
                assert "degraded_flags" in data
                assert "cache_mode" in data
                break


class TestQueryEmptyPrompt:
    def test_empty_prompt_returns_error(self):
        app, _ = _build_app()
        client = TestClient(app)

        mock_runner = MagicMock()

        async def fake_run(request):
            yield 'event: error\ndata: {"message": "请提供问题或内容"}\n\n'

        mock_runner.run = fake_run

        with patch("app.service_layer.api.query_routes._build_runner", return_value=mock_runner):
            resp = client.post(
                "/query",
                json={"session_id": "s1", "prompt": ""},
            )

        assert resp.status_code == 200
        assert "error" in resp.text


class TestRunnerContainerInjection:
    """验证 _build_runner 共享容器内存态"""

    def test_runner_prefers_container_turn_runner(self):
        from app.service_layer.api.query_routes import _build_runner
        from app.agent_layer.orchestration.turn_runner import TurnRunner

        app, container = _build_app()
        real_runner = TurnRunner(
            chat_model=container.chat_model,
            snapshot_builder=MagicMock(),
            retrieval_gate=MagicMock(),
            source_mapper=MagicMock(),
            block_streamer=MagicMock(),
            window_store=container.conversation_window,
            editor_context_store=container.editor_context_store,
            persistence=container.session_persistence,
        )
        container.turn_runner = real_runner
        mock_request = MagicMock()
        mock_request.app.state.container = container

        runner = _build_runner(mock_request)

        assert runner is real_runner

    def test_runner_uses_container_turn_runner(self):
        from app.service_layer.api.query_routes import _build_runner

        mock_request = MagicMock()
        mock_runner = MagicMock()
        _, container = _build_app(turn_runner=mock_runner)
        mock_request.app.state.container = container

        runner = _build_runner(mock_request)

        assert runner is mock_runner

    def test_runner_falls_back_when_container_missing(self):
        from app.service_layer.api.query_routes import _build_runner

        mock_request = MagicMock()
        mock_request.app.state.container = None

        runner = _build_runner(mock_request)

        assert runner._window_store is not None
        assert runner._editor_context_store is not None
        assert runner._persistence is not None
