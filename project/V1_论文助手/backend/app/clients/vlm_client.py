"""Kimi VLM 图片理解客户端

必须携带特殊 headers：
  - User-Agent: claude-code
  - anthropic-version: 2023-06-01
"""

from __future__ import annotations

import base64
import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger("paper-assistant")

_HEADERS = {
    "anthropic-version": "2023-06-01",
    "User-Agent": "claude-code",
    "Content-Type": "application/json",
}


class VLMClient:
    """Kimi Coding API 图片描述"""

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.kimi_api_key
        self._base_url = settings.kimi_base_url
        self._model = settings.kimi_model
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _build_headers(self) -> dict[str, str]:
        return {
            **_HEADERS,
            "x-api-key": self._api_key,
        }

    async def describe_image(
        self,
        image_path: str,
        prompt: str = "请详细描述这张图片的内容，特别关注与学术论文相关的信息（如公式、图表、实验结果等）。",
    ) -> str:
        if not self._api_key:
            logger.warning("Kimi API key not set, skipping image description")
            return "description unavailable"

        with open(image_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()

        ext = image_path.rsplit(".", 1)[-1].lower()
        media_type = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "webp": "image/webp",
        }.get(ext, "image/png")

        client = await self._get_client()
        body = {
            "model": self._model,
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_data}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }

        try:
            resp = await client.post(
                self._base_url,
                headers=self._build_headers(),
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("content", [])
            if content and isinstance(content, list):
                return content[0].get("text", "description unavailable")
            if isinstance(content, str):
                return content
            return "description unavailable"
        except Exception as e:
            logger.warning("VLM describe failed for %s: %s", image_path, e)
            return "description unavailable"
