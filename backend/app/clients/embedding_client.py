"""Embedding 客户端（OpenAI 兼容协议）"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.core.config import get_settings
from app.utils import error_handler

logger = logging.getLogger("paper-assistant")

_BATCH_SIZE = 32
_MAX_CONCURRENCY = 20
_MAX_RETRIES = 3


class EmbeddingClient:
    def __init__(self):
        settings = get_settings()
        self._api_key = settings.embedding_api_key
        # 约定：配置存 base URL（如 https://api.siliconflow.cn/v1），客户端追加 /embeddings
        self._base_url = settings.embedding_base_url.rstrip("/") + "/embeddings"
        self._model = settings.embedding_model
        self._dimension = settings.embedding_dimensions
        self._client: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        batches = [
            texts[i : i + _BATCH_SIZE] for i in range(0, len(texts), _BATCH_SIZE)
        ]
        tasks = [self._embed_batch(batch) for batch in batches]
        results = await asyncio.gather(*tasks)
        vectors: list[list[float]] = []
        for batch_result in results:
            vectors.extend(batch_result)
        return vectors

    async def embed_single(self, text: str) -> list[float]:
        results = await self.embed([text])
        return results[0]

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        async with self._semaphore:
            last_error: Exception | None = None
            for attempt in range(_MAX_RETRIES):
                try:
                    return await self._call_api(texts)
                except Exception as e:
                    last_error = e
                    if not error_handler.is_retryable(e) or attempt == _MAX_RETRIES - 1:
                        raise
                    backoff = error_handler.get_backoff(attempt, e)
                    logger.warning("Embedding 失败，%.1fs 后重试 (%d/%d): %s",
                                   backoff, attempt + 1, _MAX_RETRIES, e)
                    await asyncio.sleep(backoff)
            raise last_error  # type: ignore[misc]

    async def _call_api(self, texts: list[str]) -> list[list[float]]:
        client = await self._get_client()
        resp = await client.post(
            self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "input": texts,
                "encoding_format": "float",
                "dimensions": self._dimension,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
        return [item["embedding"] for item in items]
