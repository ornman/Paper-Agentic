"""LLM 对话客户端

自动检测 Kimi Coding API：
  - Kimi Coding（api.kimi.com/coding）→ Anthropic 消息格式 + 特殊 headers
  - 其他 → OpenAI 兼容协议（openai SDK）
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx
from openai import AsyncOpenAI

from app.core.config import get_settings

logger = logging.getLogger("paper-assistant")

_KIMI_HEADERS = {
    "anthropic-version": "2023-06-01",
    "User-Agent": "Roo Code",
    "Content-Type": "application/json",
}

_KIMI_ENDPOINT = "/messages"


def _is_kimi_coding(base_url: str) -> bool:
    return "kimi.com/coding" in base_url.lower()


class LLMClient:
    def __init__(self):
        settings = get_settings()
        self._api_key = settings.llm_api_key
        self._base_url = settings.llm_base_url
        self._model = settings.llm_model
        self._max_tokens = settings.llm_max_tokens
        self._temperature = settings.llm_temperature
        self._kimi_mode = _is_kimi_coding(settings.llm_base_url)

        if self._kimi_mode:
            self._httpx_client = httpx.AsyncClient(
                headers={**_KIMI_HEADERS, "x-api-key": self._api_key},
                timeout=settings.llm_timeout,
            )
            self._openai_client = None
        else:
            self._openai_client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=settings.llm_timeout,
            )
            self._httpx_client = None

    # --- 公共接口 ---

    async def chat(self, messages: list[dict]) -> str:
        if self._kimi_mode:
            return await self._kimi_chat(messages)
        return await self._openai_chat(messages)

    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        if self._kimi_mode:
            async for chunk in self._kimi_chat_stream(messages):
                yield chunk
        else:
            async for chunk in self._openai_chat_stream(messages):
                yield chunk

    async def close(self) -> None:
        if self._httpx_client:
            await self._httpx_client.aclose()
        if self._openai_client:
            await self._openai_client.close()

    # --- OpenAI 模式 ---

    async def _openai_chat(self, messages: list[dict]) -> str:
        response = await self._openai_client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            stream=False,
        )
        return response.choices[0].message.content or ""

    async def _openai_chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        stream = await self._openai_client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content is not None:
                yield delta.content

    # --- Kimi Coding 模式（Anthropic 消息格式） ---

    async def _kimi_chat(self, messages: list[dict]) -> str:
        payload = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": self._convert_messages_to_anthropic(messages),
            "stream": False,
        }

        response = await self._httpx_client.post(
            f"{self._base_url}{_KIMI_ENDPOINT}",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        content = data.get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", "")
        return ""

    async def _kimi_chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        payload = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": self._convert_messages_to_anthropic(messages),
            "stream": True,
        }

        async with self._httpx_client.stream(
            "POST",
            f"{self._base_url}{_KIMI_ENDPOINT}",
            json=payload,
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if not data_str or data_str == "[DONE]":
                    continue
                try:
                    data = json.loads(data_str)
                    if data.get("type") == "content_block_delta":
                        text = data.get("delta", {}).get("text", "")
                        if text:
                            yield text
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    @staticmethod
    def _convert_messages_to_anthropic(messages: list[dict]) -> list[dict]:
        """OpenAI 格式消息 → Anthropic 格式

        OpenAI: {"role": "user", "content": "text"}
        Anthropic: {"role": "user", "content": [{"type": "text", "text": "text"}]}
        """
        result = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, str):
                result.append({"role": role, "content": [{"type": "text", "text": content}]})
            else:
                result.append(msg)
        return result
