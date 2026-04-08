# Reranker 客户端
# 调用硅基流动 Qwen3-Reranker-8B
import httpx
from typing import List
from app.core.config import get_settings


class RerankClient:
    """Reranker 客户端，调用硅基流动 API"""

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.rerank_api_key
        self._base_url = settings.rerank_base_url
        self._model = settings.rerank_model

    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        """
        重排序文档

        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回数量

        Returns:
            [(document_index, relevance_score), ...]
        """
        if not documents:
            return []

        async with httpx.AsyncClient(timeout=60.0) as client:
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
