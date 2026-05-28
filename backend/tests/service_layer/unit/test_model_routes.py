"""model_routes 单元测试"""

from __future__ import annotations

from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _build_app():
    from app.service_layer.api.model_routes import router

    app = FastAPI()
    app.include_router(router)
    return app


class TestDiscoverModels:
    @patch("app.service_layer.api.model_routes.AsyncOpenAI")
    def test_returns_model_list(self, mock_openai_cls):
        mock_client = AsyncMock()
        mock_models_resp = MagicMock()
        mock_models_resp.data = [
            MagicMock(id="gpt-4", owned_by="openai"),
            MagicMock(id="gpt-3.5-turbo", owned_by="openai"),
        ]
        mock_client.models.list.return_value = mock_models_resp
        mock_client.close = AsyncMock()
        mock_openai_cls.return_value = mock_client

        app = _build_app()
        client = TestClient(app)
        resp = client.post("/models", json={
            "api_key": "test-key",
            "api_url": "https://api.openai.com/v1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert len(data["models"]) == 2
        assert data["models"][0]["id"] == "gpt-4"

    @patch("app.service_layer.api.model_routes.AsyncOpenAI")
    def test_handles_api_error(self, mock_openai_cls):
        mock_client = AsyncMock()
        mock_client.models.list.side_effect = Exception("connection refused")
        mock_client.close = AsyncMock()
        mock_openai_cls.return_value = mock_client

        app = _build_app()
        client = TestClient(app)
        resp = client.post("/models", json={
            "api_key": "bad-key",
            "api_url": "https://invalid.example.com/v1",
        })
        assert resp.status_code == 502
        assert "模型列表获取失败" in resp.json()["detail"]

    def test_missing_fields_returns_422(self):
        app = _build_app()
        client = TestClient(app)
        resp = client.post("/models", json={"api_key": "only-key"})
        assert resp.status_code == 422
