# Rerank 客户端（硅基流动实现）
# 调用硅基流动 Qwen3-Reranker-8B
from __future__ import annotations

import httpx

from app.clients.vlm_client import RerankClient as RerankClientBase
from app.core.config import get_settings
from app.core.retry import retry_async


class RerankClient(RerankClientBase):
    """硅基流动 Rerank 客户端实现.

    实现 RerankClientBase 抽象接口。
    可替换为其他实现（Cohere、Jina 等）。
    """

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.siliconflow_api_key
        self._base_url = f"{settings.siliconflow_base_url.rstrip('/')}/rerank"
        self._model = settings.rerank_model
        self._timeout = settings.siliconflow_timeout

    @retry_async(max_retries=3)
    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        """重排序文档（带重试）.

        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回数量

        Returns:
            [(document_index, relevance_score), ...]
        """
        if not documents:
            return []

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "query": query,
                    "documents": documents,
                    "top_k": min(top_k, len(documents)),
                    "return_documents": False,
                },
            )
            response.raise_for_status()
            data = response.json()

        # 提取结果
        results = data.get("results", [])
        return [
            (r["index"], r["relevance_score"])
            for r in results
        ]
