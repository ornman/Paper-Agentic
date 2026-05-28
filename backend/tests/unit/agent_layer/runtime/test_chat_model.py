"""chat_model 单元测试：429 重试 + 模型轮转"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import RateLimitError

from app.agent_layer.runtime.chat_model import ChatModel
from app.service_layer.config.settings import BackendSettings


def _make_settings(**overrides) -> BackendSettings:
    defaults = {
        "llm_api_key": "test-key",
        "llm_base_url": "http://test/v1",
        "llm_model": "primary-model",
        "llm_fallback_models": "fallback-a,fallback-b",
        "llm_max_tokens": 100,
        "llm_temperature": 0.5,
        "llm_timeout": 10.0,
    }
    defaults.update(overrides)
    return BackendSettings(**defaults)


def _mock_429_response():
    """构造一个模拟的 429 响应对象"""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "1"}
    mock_response.json.return_value = {"error": {"message": "rate limited"}}
    return mock_response


# ──────────────────────────────────────────────
# 模型链构造
# ──────────────────────────────────────────────
class TestModelChain:
    def test_primary_plus_fallbacks(self):
        settings = _make_settings()
        model = ChatModel(settings)
        chain = model._model_chain(None)
        assert chain == ["primary-model", "fallback-a", "fallback-b"]

    def test_explicit_model_not_duplicated(self):
        settings = _make_settings(llm_fallback_models="primary-model,other")
        model = ChatModel(settings)
        chain = model._model_chain("primary-model")
        assert chain == ["primary-model", "other"]
        assert chain.count("primary-model") == 1

    def test_no_fallbacks(self):
        settings = _make_settings(llm_fallback_models="")
        model = ChatModel(settings)
        chain = model._model_chain(None)
        assert chain == ["primary-model"]

    def test_explicit_override_first(self):
        settings = _make_settings()
        model = ChatModel(settings)
        chain = model._model_chain("custom-model")
        assert chain[0] == "custom-model"


# ──────────────────────────────────────────────
# chat() 429 重试
# ──────────────────────────────────────────────
class TestChat429Retry:
    @pytest.mark.asyncio
    async def test_fallback_on_429(self):
        """主模型 429 → 自动切 fallback-a 成功"""
        settings = _make_settings()
        model = ChatModel(settings)

        mock_choice = MagicMock()
        mock_choice.message.content = "fallback reply"

        call_models = []

        async def fake_create(**kwargs):
            call_models.append(kwargs["model"])
            if kwargs["model"] == "primary-model":
                raise RateLimitError(
                    message="rate limited",
                    response=_mock_429_response(),
                    body={"error": {"message": "rate limited"}},
                )
            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]
            return mock_resp

        model._client = MagicMock()
        model._client.chat.completions.create = AsyncMock(side_effect=fake_create)

        with patch("app.agent_layer.runtime.chat_model.asyncio.sleep", new_callable=AsyncMock):
            result = await model.chat([{"role": "user", "content": "hi"}])

        assert result == "fallback reply"
        assert call_models == ["primary-model", "fallback-a"]

    @pytest.mark.asyncio
    async def test_all_429_raises_last(self):
        """所有模型都 429 → 抛出最后一个 RateLimitError"""
        settings = _make_settings()
        model = ChatModel(settings)

        async def fake_create(**kwargs):
            raise RateLimitError(
                message="rate limited",
                response=_mock_429_response(),
                body={"error": {"message": "rate limited"}},
            )

        model._client = MagicMock()
        model._client.chat.completions.create = AsyncMock(side_effect=fake_create)

        with patch("app.agent_layer.runtime.chat_model.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RateLimitError):
                await model.chat([{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_non_429_not_caught(self):
        """非 429 异常（如 500）不触发重试，直接抛出"""
        settings = _make_settings()
        model = ChatModel(settings)

        call_count = 0

        async def fake_create(**kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("server error")

        model._client = MagicMock()
        model._client.chat.completions.create = AsyncMock(side_effect=fake_create)

        with pytest.raises(RuntimeError, match="server error"):
            await model.chat([{"role": "user", "content": "hi"}])
        assert call_count == 1  # 只调了一次，没重试

    @pytest.mark.asyncio
    async def test_primary_success_no_fallback(self):
        """主模型成功 → 不尝试 fallback"""
        settings = _make_settings()
        model = ChatModel(settings)

        mock_choice = MagicMock()
        mock_choice.message.content = "ok"

        async def fake_create(**kwargs):
            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]
            return mock_resp

        model._client = MagicMock()
        model._client.chat.completions.create = AsyncMock(side_effect=fake_create)

        result = await model.chat([{"role": "user", "content": "hi"}])
        assert result == "ok"
        model._client.chat.completions.create.assert_called_once()


# ──────────────────────────────────────────────
# chat_stream() 429 重试
# ──────────────────────────────────────────────
class TestChatStream429Retry:
    @pytest.mark.asyncio
    async def test_stream_fallback_on_429(self):
        """chat_stream 主模型 429 → fallback-a 成功"""
        settings = _make_settings()
        model = ChatModel(settings)

        call_models = []

        async def fake_create(**kwargs):
            call_models.append(kwargs["model"])
            if kwargs["model"] == "primary-model":
                raise RateLimitError(
                    message="rate limited",
                    response=_mock_429_response(),
                    body={"error": {"message": "rate limited"}},
                )

            async def fake_stream():
                chunk = MagicMock()
                chunk.choices = [MagicMock()]
                chunk.choices[0].delta.content = "stream-ok"
                yield chunk

            return fake_stream()

        model._client = MagicMock()
        model._client.chat.completions.create = AsyncMock(side_effect=fake_create)

        with patch("app.agent_layer.runtime.chat_model.asyncio.sleep", new_callable=AsyncMock):
            chunks = []
            async for c in model.chat_stream([{"role": "user", "content": "hi"}]):
                chunks.append(c)

        assert chunks == ["stream-ok"]
        assert call_models == ["primary-model", "fallback-a"]

    @pytest.mark.asyncio
    async def test_stream_all_429_raises(self):
        """chat_stream 所有模型 429 → 抛异常"""
        settings = _make_settings()
        model = ChatModel(settings)

        async def fake_create(**kwargs):
            raise RateLimitError(
                message="rate limited",
                response=_mock_429_response(),
                body={"error": {"message": "rate limited"}},
            )

        model._client = MagicMock()
        model._client.chat.completions.create = AsyncMock(side_effect=fake_create)

        with patch("app.agent_layer.runtime.chat_model.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RateLimitError):
                async for _ in model.chat_stream([{"role": "user", "content": "hi"}]):
                    pass


# ──────────────────────────────────────────────
# Retry-After header 解析
# ──────────────────────────────────────────────
class TestRetryAfterHeader:
    def test_reads_retry_after_header(self):
        """应优先使用 Retry-After header 的值"""
        mock_resp = MagicMock()
        mock_resp.headers = {"retry-after": "5"}
        exc = RateLimitError(message="rate limited", response=mock_resp, body={})
        wait = ChatModel._backoff_seconds(exc)
        assert wait == 5.0

    def test_retry_after_with_caps(self):
        """Retry-After header 大小写不敏感"""
        mock_resp = MagicMock()
        mock_resp.headers = {"Retry-After": "3"}
        exc = RateLimitError(message="rate limited", response=mock_resp, body={})
        wait = ChatModel._backoff_seconds(exc)
        assert wait == 3.0

    def test_fallback_when_no_header(self):
        """无 Retry-After header 时使用随机退避"""
        mock_resp = MagicMock()
        mock_resp.headers = {}
        exc = RateLimitError(message="rate limited", response=mock_resp, body={})
        wait = ChatModel._backoff_seconds(exc)
        assert 0.5 <= wait <= 2.0

    def test_retry_after_minimum(self):
        """Retry-After 值过小时保证最小退避"""
        mock_resp = MagicMock()
        mock_resp.headers = {"retry-after": "0.1"}
        exc = RateLimitError(message="rate limited", response=mock_resp, body={})
        wait = ChatModel._backoff_seconds(exc)
        assert wait >= 0.5

    def test_retry_after_invalid_header(self):
        """Retry-After 非数值时退化为随机退避"""
        mock_resp = MagicMock()
        mock_resp.headers = {"retry-after": "not-a-number"}
        exc = RateLimitError(message="rate limited", response=mock_resp, body={})
        wait = ChatModel._backoff_seconds(exc)
        assert 0.5 <= wait <= 2.0
