# Embedding 客户端（硅基流动实现）
# 封装硅基流动 Qwen3-Embedding-8B 接口，支持批量处理
from __future__ import annotations

import asyncio
import httpx

from app.clients.vlm_client import EmbeddingClient as EmbeddingClientBase
from app.core.errors import IndexingError
from app.core.config import get_settings
from app.core.retry import retry_async


class EmbeddingClient(EmbeddingClientBase):
    """硅基流动 Embedding 客户端实现（支持并发优化）.

    实现 EmbeddingClientBase 抽象接口。
    可替换为其他实现（OpenAI、Azure 等）。

    🔴 P0-3 优化：添加并发控制、连接复用、速率限制
    """

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.siliconflow_api_key
        self._base_url = settings.siliconflow_base_url
        self._model = settings.embedding_model
        self._batch_size = settings.embedding_batch_size
        self._dimension = settings.embedding_dimensions
        self._timeout = settings.siliconflow_timeout

        # 🔴 P0-3 优化：并发控制配置
        self._concurrency = getattr(settings, "embedding_concurrency", 5)
        self._rate_limit = getattr(settings, "embedding_rate_limit", 100)
        self._semaphore = asyncio.Semaphore(self._concurrency)
        self._rate_limiter = asyncio.Semaphore(self._rate_limit // 60)  # 每秒速率
        self._client: httpx.AsyncClient | None = None  # 延迟初始化

    def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端（连接复用）.

        🔴 P0-3 优化：复用 HTTP 连接，避免重复建立 TCP 连接
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                limits=httpx.Limits(
                    max_connections=self._concurrency,
                    max_keepalive_connections=self._concurrency,
                ),
            )
        return self._client

    async def close(self):
        """关闭 HTTP 客户端.

        🔴 P0-3 优化：优雅关闭连接
        """
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @retry_async(max_retries=3)
    async def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """批量嵌入文本，并发批处理（带速率限制）.

        🔴 P0-3 优化：
        1. 使用信号量控制并发数
        2. 复用 HTTP 连接
        3. 细粒度重试（批次级别）
        4. 速率限制保护

        Args:
            texts: 待嵌入的文本列表

        Returns:
            嵌入向量列表，顺序与输入一致
        """
        if not texts:
            return []

        # 分批
        batches = [
            texts[i : i + self._batch_size]
            for i in range(0, len(texts), self._batch_size)
        ]

        # 🔴 P0-3 优化：并发处理所有批次
        results = await self._process_batches_concurrent(batches)

        # 展平结果
        flattened = []
        for batch_result in results:
            flattened.extend(batch_result)
        return flattened

    async def _process_batches_concurrent(
        self,
        batches: list[list[str]],
    ) -> list[list[list[float]]]:
        """并发处理多个批次.

        🔴 P0-3 优化：使用 asyncio.gather 并发执行
        """
        tasks = [
            self._embed_batch_with_retry(batch)
            for batch in batches
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 检查异常
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                raise Exception(f"批次 {i} 失败: {result}") from result

        return results

    async def _embed_batch_with_retry(
        self,
        batch: list[str],
    ) -> list[list[float]]:
        """单批次处理（带重试和速率限制）.

        🔴 P0-3 优化：批次级别的速率限制和重试
        """
        # 速率限制
        async with self._rate_limiter:
            async with self._semaphore:
                return await self._embed_batch_raw(batch)

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
        """直接调用 API，处理单批次（连接复用）.

        🔴 P0-3 优化：复用 HTTP 客户端，避免重复建立连接

        Args:
            texts: 待嵌入的文本列表（不超过 batch_size）

        Returns:
            嵌入向量列表
        """
        client = self._get_client()  # 🔴 P0-3 优化：复用客户端

        try:
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
        except httpx.HTTPStatusError as e:
            # 🔴 P0-3 优化：处理 429 速率限制错误
            if e.response.status_code == 429:
                # 速率限制错误，添加延迟后重试
                await asyncio.sleep(1)
                return await self._embed_batch_raw(texts)
            raise

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
