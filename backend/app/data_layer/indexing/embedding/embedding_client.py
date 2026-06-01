"""Embedding 客户端"""

from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger("paper-assistant")


def _estimate_tokens(text: str) -> int:
    """估算 token 数（与 semantic_chunker.estimate_tokens 同逻辑）"""
    count = 0.0
    for ch in text:
        count += 1.5 if "一" <= ch <= "鿿" else 0.75
    return int(count)


class EmbeddingClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        model: str,
        dimensions: int,
        timeout: float,
        batch_size: int,
        max_concurrency: int,
        context_window: int = 0,
    ) -> None:
        from app.service_layer.config.settings import get_settings
        _s = get_settings()
        self._api_key = api_key
        self._base_url = base_url.rstrip("/") + "/embeddings"
        self._model = model
        self._dimensions = dimensions
        self._timeout = timeout
        self._batch_size = batch_size
        self._max_concurrency = max_concurrency
        self._context_window = context_window or _s.embedding_context_window or _s.chunk_max_context
        self._client: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(self._max_concurrency)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # tokenizer 长度校验
        for i, text in enumerate(texts):
            est = _estimate_tokens(text)
            if est > self._context_window:
                raise ValueError(
                    f"text[{i}] 超出 embedding 模型 token 上限: "
                    f"估算 {est} tokens > {self._context_window}。"
                    f"请在切分阶段控制 chunk 大小。"
                )

        batches = [texts[i : i + self._batch_size] for i in range(0, len(texts), self._batch_size)]
        results = await asyncio.gather(*[self._embed_batch(batch) for batch in batches])
        vectors: list[list[float]] = []
        for batch_result in results:
            vectors.extend(batch_result)
        return vectors

    async def embed_single(self, text: str) -> list[float]:
        return (await self.embed([text]))[0]

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        async with self._semaphore:
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    return await self._call_api(texts)
                except Exception as exc:
                    last_error = exc
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 ** attempt)
            raise last_error  # type: ignore[misc]

    async def _call_api(self, texts: list[str]) -> list[list[float]]:
        client = await self._get_client()
        response = await client.post(
            self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "input": texts,
                "encoding_format": "float",
                "dimensions": self._dimensions,
            },
        )
        response.raise_for_status()
        data = response.json()
        items = sorted(data.get("data", []), key=lambda item: item.get("index", 0))
        return [item["embedding"] for item in items]
