"""HTTP 级 E2E 测试：经过 FastAPI StreamingResponse 的完整链路"""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.service_layer.bootstrap.app_factory import create_app

app = create_app()


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_http_query_basic(client):
    """POST /api/v1/query 返回 SSE 流，包含 block/sources/done"""
    async with client.stream(
        "POST",
        "/api/v1/query",
        json={"session_id": "http-test-1", "prompt": "1+1等于几？", "enable_rag": False},
        headers={"Accept": "text/event-stream"},
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        body = ""
        async for line in resp.aiter_text():
            body += line

    assert "event: done" in body
    assert "event: block" in body


@pytest.mark.asyncio
async def test_http_query_empty_prompt(client):
    """空 prompt 返回 error 事件，不是 500"""
    async with client.stream(
        "POST",
        "/api/v1/query",
        json={"session_id": "http-test-empty", "prompt": "", "enable_rag": False},
        headers={"Accept": "text/event-stream"},
    ) as resp:
        assert resp.status_code == 200
        body = ""
        async for line in resp.aiter_text():
            body += line

    assert "event: error" in body
    assert "event: done" not in body


@pytest.mark.asyncio
async def test_http_query_missing_prompt_returns_422(client):
    """缺少 prompt 字段：Pydantic 直接返回 422（FastAPI 自动处理）"""
    resp = await client.post(
        "/api/v1/query",
        json={"session_id": "http-test-missing"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_http_query_error_sanitized(client):
    """错误信息不暴露内部细节（空 prompt 触发的早退错误）"""
    async with client.stream(
        "POST",
        "/api/v1/query",
        json={"session_id": "http-test-err", "prompt": "", "enable_rag": False},
        headers={"Accept": "text/event-stream"},
    ) as resp:
        body = ""
        async for line in resp.aiter_text():
            body += line

    for segment in body.split("\n\n"):
        if "event: error" in segment:
            data_line = [l for l in segment.split("\n") if l.startswith("data:")]
            if data_line:
                data = json.loads(data_line[0].replace("data: ", ""))
                msg = data.get("message", "")
                assert "Traceback" not in msg
                assert "openai" not in msg.lower()
                assert ".py" not in msg
                break


@pytest.mark.asyncio
async def test_http_query_multi_turn(client):
    """同 session 多轮对话通过 HTTP 保持上下文"""
    sid = "http-multiturn-1"

    async with client.stream(
        "POST",
        "/api/v1/query",
        json={"session_id": sid, "prompt": "什么是深度学习？", "enable_rag": False},
    ) as resp:
        body1 = ""
        async for line in resp.aiter_text():
            body1 += line

    assert "event: done" in body1

    async with client.stream(
        "POST",
        "/api/v1/query",
        json={"session_id": sid, "prompt": "它和机器学习有什么关系？", "enable_rag": False},
    ) as resp:
        body2 = ""
        async for line in resp.aiter_text():
            body2 += line

    assert "event: done" in body2
    assert "event: block" in body2


@pytest.mark.asyncio
async def test_http_query_extra_fields_ignored(client):
    """额外字段应被忽略，不影响请求处理"""
    async with client.stream(
        "POST",
        "/api/v1/query",
        json={
            "session_id": "http-test-extra",
            "prompt": "你好",
            "enable_rag": False,
            "unknown_field": "should_be_ignored",
            "another": 123,
        },
    ) as resp:
        assert resp.status_code == 200
        body = ""
        async for line in resp.aiter_text():
            body += line

    assert "event: done" in body
