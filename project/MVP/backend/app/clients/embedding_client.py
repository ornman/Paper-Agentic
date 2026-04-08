# Embedding 客户端
# 封装硅基流动 Qwen3-Embedding-8B 接口，支持批量处理
from __future__ import annotations

import httpx

from app.core.errors import IndexingError
from app.core.config import get_settings


class EmbeddingClient:
    """Embedding 客户端，调用硅基流动 Qwen3-Embedding-8B。"""

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.embedding_api_key
        self._base_url = settings.embedding_base_url
        self._model = settings.embedding_model
        self._batch_size = settings.embedding_batch_size
        self._dimension = settings.embedding_dimension

        # Task 5 需要在写入前验证 embedding 契约。
        # 因此这里显式暴露只读属性给 indexing service 使用，
        # 避免 service 反向窥探私有字段。
        self.model_name = self._model
        self.dimensions = self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        批量嵌入文本，内部自动分批处理

        Args:
            texts: 待嵌入的文本列表

        Returns:
            嵌入向量列表，顺序与输入一致
        """
        if not texts:
            return []

        results = []
        # 按 batch_size 分批处理
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            batch_embeddings = await self._embed_batch_raw(batch)
            results.extend(batch_embeddings)
        return results

    async def embed_single(self, text: str) -> list[float]:
        """
        单文本嵌入

        Args:
            text: 待嵌入文本

        Returns:
            嵌入向量（1536 维）
        """
        embeddings = await self.embed([text])
        return embeddings[0]

    async def _embed_batch_raw(self, texts: list[str]) -> list[list[float]]:
        """
        直接调用 API，处理单批次

        Args:
            texts: 待嵌入的文本列表（不超过 batch_size）

        Returns:
            嵌入向量列表
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/embeddings",
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
            response.raise_for_status()
            data = response.json()

        # 按 index 排序，确保顺序一致
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        embeddings = [item["embedding"] for item in sorted_data]

        # 这里必须在客户端层就做维度兜底。
        # 原因是：
        # 1. 上游服务端偶发漂移时，越早发现越好。
        # 2. 如果等到写入向量库再报错，脏数据可能已经部分进入系统。
        # 3. 客户端层是“外部系统返回值进入本系统”的第一道边界。
        for index, embedding in enumerate(embeddings):
            if len(embedding) != self._dimension:
                raise IndexingError(
                    code="embedding_output_dimensions_mismatch",
                    message=f"Embedding 返回向量维度必须为 {self._dimension}",
                    detail={
                        "index": index,
                        "actual_dimensions": len(embedding),
                    },
                )
        return embeddings
