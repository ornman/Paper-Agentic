# Embedding 客户端（硅基流动实现）
# 封装硅基流动 Qwen3-Embedding-8B 接口，支持批量处理
from __future__ import annotations

import httpx

from app.clients.vlm_client import EmbeddingClient as EmbeddingClientBase
from app.core.errors import IndexingError
from app.core.config import get_settings
from app.core.retry import retry_async


class EmbeddingClient(EmbeddingClientBase):
    """硅基流动 Embedding 客户端实现.

    实现 EmbeddingClientBase 抽象接口。
    可替换为其他实现（OpenAI、Azure 等）。
    """

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.siliconflow_api_key
        self._base_url = settings.siliconflow_base_url
        self._model = settings.embedding_model
        self._batch_size = settings.embedding_batch_size
        self._dimension = settings.embedding_dimensions
        self._timeout = settings.siliconflow_timeout

    @retry_async(max_retries=3)
    async def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """批量嵌入文本，内部自动分批处理（带重试）.

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

    async def embed_single(
        self,
        text: str,
    ) -> list[float]:
        """单文本嵌入.

        Args:
            text: 待嵌入文本

        Returns:
            嵌入向量（1536 维）
        """
        embeddings = await self.embed([text])
        return embeddings[0]

    @property
    def dimensions(self) -> int:
        """向量维度."""
        return self._dimension

    @property
    def model_name(self) -> str:
        """模型名称."""
        return self._model

    async def _embed_batch_raw(self, texts: list[str]) -> list[list[float]]:
        """直接调用 API，处理单批次.

        Args:
            texts: 待嵌入的文本列表（不超过 batch_size）

        Returns:
            嵌入向量列表
        """
        async with httpx.AsyncClient(timeout=self._timeout) as client:
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

        # 客户端层维度兜底
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
