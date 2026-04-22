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
        self._base_url = settings.kimi_base_url
        self._model = settings.kimi_model
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "anthropic-version": "2023-06-01",
                "User-Agent": "claude-code",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    async def chat(self, messages: list[dict]) -> str:
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
        }

        response = await self._client.post("/messages", json=payload)
        response.raise_for_status()
        data = response.json()

        # Kimi API 响应格式：{"content": [{"type": "text", "text": "..."}]}
        if "content" in data and len(data["content"]) > 0:
            return data["content"][0].get("text", "")
        return ""

    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
        }

        async with self._client.stream("POST", "/messages", json=payload) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break

                try:
                    import json

                    data = json.loads(data_str)
                    # Kimi SSE 格式：{"content": [{"type": "text", "text": "..."}]}
                    if "content" in data and len(data["content"]) > 0:
                        text = data["content"][0].get("text", "")
                        if text:
                            yield text
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    async def close(self) -> None:
        await self._client.aclose()
