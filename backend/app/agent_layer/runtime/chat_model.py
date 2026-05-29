"""OpenAI 兼容 LLM 客户端（支持 429 自动重试 + 模型轮转 + 上下文长度自动发现）"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import AsyncIterator

from openai import AsyncOpenAI, RateLimitError

from app.service_layer.config.settings import BackendSettings

logger = logging.getLogger("paper-assistant")


class ChatModel:
    def __init__(self, settings: BackendSettings):
        self._api_key = settings.llm_api_key
        self._base_url = settings.llm_base_url
        self._model = settings.llm_model
        self._max_tokens = settings.llm_max_tokens
        self._temperature = settings.llm_temperature
        self._timeout = settings.llm_timeout
        self._fallback_models = settings.llm_fallback_list
        self._client: AsyncOpenAI | None = None
        self.max_context_tokens: int = settings.llm_context_window or settings.context_window_tokens

        if self._api_key and self._base_url:
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
            )

    def _model_chain(self, model: str | None) -> list[str]:
        """返回模型尝试顺序：[请求指定模型/主模型] + fallback 列表，去重"""
        primary = model or self._model
        chain = [primary]
        for m in self._fallback_models:
            if m not in chain:
                chain.append(m)
        return chain

    async def discover_context_window(self, model: str | None = None) -> int:
        """从 API 自动发现模型上下文长度

        部分提供商在 GET /models/{model_id} 返回 context_window 字段。
        发现失败返回 0（由调用方 fallback）。
        """
        if not self._client:
            return 0
        target = model or self._model
        try:
            model_info = await self._client.models.retrieve(target)
            ctx = getattr(model_info, "context_window", None)
            if ctx and isinstance(ctx, int) and ctx > 0:
                logger.info("模型 %s 上下文长度: %d", target, ctx)
                return ctx
        except Exception as e:
            logger.debug("模型上下文发现失败 (%s): %s", target, e)
        return 0

    @staticmethod
    def _backoff_seconds(exc: RateLimitError) -> float:
        """从 Retry-After header 读取等待时间，否则随机退避"""
        retry_after = getattr(exc, "response", None)
        if retry_after is not None:
            header = retry_after.headers.get("retry-after") or retry_after.headers.get("Retry-After")
            if header:
                try:
                    return max(float(header), 0.5)
                except (ValueError, TypeError):
                    pass
        return random.uniform(0.5, 2.0)

    async def chat(self, messages: list[dict], model: str | None = None) -> str:
        if self._client is None:
            raise RuntimeError("LLM client not initialized")

        last_exc: Exception | None = None
        for attempt_model in self._model_chain(model):
            try:
                response = await self._client.chat.completions.create(
                    model=attempt_model,
                    messages=messages,
                    max_tokens=self._max_tokens,
                    temperature=self._temperature,
                    stream=False,
                )
                return response.choices[0].message.content or ""
            except RateLimitError as exc:
                last_exc = exc
                wait = self._backoff_seconds(exc)
                logger.warning(
                    "429 rate limit on model %s, rotating to next after %.1fs",
                    attempt_model,
                    wait,
                )
                await asyncio.sleep(wait)
            except Exception:
                raise
        raise last_exc  # type: ignore[misc]

    async def chat_stream(
        self, messages: list[dict], model: str | None = None
    ) -> AsyncIterator[str]:
        if self._client is None:
            raise RuntimeError("LLM client not initialized")

        last_exc: Exception | None = None
        for attempt_model in self._model_chain(model):
            try:
                stream = await self._client.chat.completions.create(
                    model=attempt_model,
                    messages=messages,
                    max_tokens=self._max_tokens,
                    temperature=self._temperature,
                    stream=True,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta.content is not None:
                        yield delta.content
                return  # 成功完成，退出重试循环
            except RateLimitError as exc:
                last_exc = exc
                wait = self._backoff_seconds(exc)
                logger.warning(
                    "429 rate limit on model %s, rotating to next after %.1fs",
                    attempt_model,
                    wait,
                )
                await asyncio.sleep(wait)
            except Exception:
                raise
        raise last_exc  # type: ignore[misc]

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
