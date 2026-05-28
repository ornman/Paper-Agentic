"""query_routes 单元测试"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _build_app(*, redis_ok=False, has_editor_store=True, has_window_store=True):
    """构造带 mock container 的 FastAPI app"""
    from app.service_layer.api.query_routes import router

    app = FastAPI()
    app.include_router(router)

    container = MagicMock()
    container.chat_model = MagicMock()
    container.chat_model.max_context_tokens = 32000
    container.vector_store = MagicMock()
    container.keyword_search = MagicMock()
    container.embedding_client = MagicMock()
    container.redis_health = {"status": "ok" if redis_ok else "unavailable"}
    container.conversation_window = MagicMock() if has_window_store else None
    container.editor_context_store = MagicMock() if has_editor_store else None

    app.state.container = container
    return app, container


class TestQueryMetadataEvent:
    """验证首个 SSE 帧是 metadata 事件"""

    def test_first_frame_is_metadata(self):
        app, container = _build_app()
        client = TestClient(app)

        mock_runner = MagicMock()

        async def fake_run(request):
            yield 'event: metadata\ndata: {"request_id":"r1","session_id":"s1","used_inputs":{"prompt":1.0,"selection":0.0,"written_context":0.0,"rag_evidence":0.0},"context_tokens":10,"remaining_tokens":31990,"remaining_ratio":0.9997,"retrieval_planned":true,"degraded_flags":[],"redis_mode":"unavailable"}\n\n'
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
            yield 'event: metadata\ndata: {"request_id":"r1","session_id":"s1","used_inputs":{"prompt":1.0},"context_tokens":10,"remaining_tokens":31990,"remaining_ratio":0.9997,"retrieval_planned":true,"degraded_flags":[],"redis_mode":"unavailable"}\n\n'
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
                assert "redis_mode" in data
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
    """验证 _build_runner 从 container 取依赖"""

    def test_runner_uses_container_deps(self):
        from app.service_layer.api.query_routes import _build_runner

        mock_request = MagicMock()
        container = MagicMock()
        container.chat_model = MagicMock()
        container.chat_model.max_context_tokens = 32000
        container.vector_store = MagicMock(name="vs")
        container.keyword_search = MagicMock(name="kw")
        container.embedding_client = MagicMock(name="ec")
        container.conversation_window = MagicMock(name="cw")
        container.editor_context_store = MagicMock(name="ecs")
        container.redis_health = {"status": "ok"}
        mock_request.app.state.container = container

        runner = _build_runner(mock_request)

        assert runner._vector_store is container.vector_store
        assert runner._keyword_search is container.keyword_search
        assert runner._embedding_client is container.embedding_client
        assert runner._redis_mode == "connected"

    def test_runner_degraded_without_redis(self):
        """conversation_window 存在但 Redis 不 ok → degraded"""
        from app.service_layer.api.query_routes import _build_runner

        mock_request = MagicMock()
        container = MagicMock()
        container.chat_model = MagicMock()
        container.chat_model.max_context_tokens = 32000
        container.vector_store = MagicMock()
        container.keyword_search = MagicMock()
        container.embedding_client = MagicMock()
        container.conversation_window = MagicMock()
        container.editor_context_store = MagicMock()
        container.redis_health = {"status": "unavailable"}
        mock_request.app.state.container = container

        runner = _build_runner(mock_request)
        assert runner._redis_mode == "degraded"

    def test_runner_fallback_when_no_window_store(self):
        from app.service_layer.api.query_routes import _build_runner

        mock_request = MagicMock()
        container = MagicMock()
        container.chat_model = MagicMock()
        container.chat_model.max_context_tokens = 32000
        container.vector_store = MagicMock()
        container.keyword_search = MagicMock()
        container.embedding_client = MagicMock()
        container.conversation_window = None
        container.editor_context_store = None
        container.redis_health = {"status": "unavailable"}
        mock_request.app.state.container = container

        runner = _build_runner(mock_request)
        assert runner._window_store is not None
        assert runner._editor_context_store is not None
