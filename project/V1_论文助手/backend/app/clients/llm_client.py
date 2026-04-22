"""LLM 对话客户端（Kimi Coding API）"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx

from app.core.config import get_settings

logger = logging.getLogger("paper-assistant")


class LLMClient:
    def __init__(self):
        settings = get_settings()
        self._api_key = settings.kimi_api_key
        # base_url 已经包含完整路径：https://api.kimi.com/coding/v1/messages
        self._endpoint_url = settings.kimi_base_url
        self._model = settings.kimi_model
        self._client = httpx.AsyncClient(
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "User-Agent": "claude-code",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    async def chat(self, messages: list[dict]) -> str:
        payload = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": messages,
            "stream": False,
        }

        response = await self._client.post(self._endpoint_url, json=payload)
        response.raise_for_status()
        data = response.json()

        if "content" in data and len(data["content"]) > 0:
            return data["content"][0].get("text", "")
        return ""

    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        import json

        payload = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": messages,
            "stream": True,
        }

        async with self._client.stream("POST", self._endpoint_url, json=payload) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue

                data_str = line[5:].strip()
                if not data_str or data_str == "[DONE]":
                    continue

                try:
                    data = json.loads(data_str)
                    # Anthropic 风格 SSE：
                    # content_block_delta → delta.text
                    if data.get("type") == "content_block_delta":
                        delta = data.get("delta", {})
                        text = delta.get("text", "")
                        if text:
                            yield text
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    async def close(self) -> None:
        await self._client.aclose()
