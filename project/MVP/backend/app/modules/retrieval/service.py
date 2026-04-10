# 检索服务（新架构）
# 支持分布式多 Collection 检索 + RRF 融合 + Rerank

from __future__ import annotations

from typing import Any

from app.clients.embedding_client import EmbeddingClient
from app.clients.rerank_client import RerankClient
from app.stores.qdrant_store import QdrantStore


class RetrievalService:
    """检索服务."""

    def __init__(
        self,
        *,
        qdrant_store: QdrantStore | None = None,
        embedding_client: EmbeddingClient | None = None,
        rerank_client: RerankClient | None = None,
    ) -> None:
        self.qdrant_store = qdrant_store or QdrantStore()
        self.embedding_client = embedding_client or EmbeddingClient()
        self.rerank_client = rerank_client or RerankClient()

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        resource_types: list[str] | None = None,
        selected_papers: list[str] | None = None,
    ) -> dict[str, Any]:
        """混合检索：向量检索 + Rerank.

        Args:
            query: 查询文本
            top_k: 返回数量
            resource_types: 资源类型过滤（预留接口，暂未实现）
            selected_papers: 用户选择的论文 ID 列表（预留接口，暂未实现）

        Returns:
            检索结果
        """
        # 🔮 未来扩展：Collection 过滤逻辑
        # if selected_papers:
        #     collections = [f"paper_{pid}" for pid in selected_papers]
        # else:
        #     collections = self.qdrant_store.list_all_collections()

        # 阶段1: 向量检索
        query_vector = await self.embedding_client.embed_single(query)
        vector_results = self.qdrant_store.search_all(
            query_vector=query_vector,
            limit=top_k * 2,  # 召回更多，Rerank 后筛选
        )

        # 阶段2: Rerank
        if len(vector_results) > top_k:
            rerank_texts = [r["payload"]["content"] for r in vector_results]
            rerank_scores = await self.rerank_client.rerank(
                query=query,
                documents=rerank_texts,
                top_k=top_k,
            )

            # 按 Rerank 结果重新排序
            reranked_results = []
            for doc_index, score in rerank_scores:
                result = vector_results[doc_index].copy()
                result["rerank_score"] = score
                reranked_results.append(result)

            final_results = reranked_results[:top_k]
        else:
            final_results = vector_results[:top_k]

        return {
            "query": query,
            "results": final_results,
            "total": len(final_results),
        }

    async def search_single_collection(
        self,
        paper_id: str,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """搜索单个论文 Collection.

        Args:
            paper_id: 论文 ID
            query: 查询文本
            limit: 返回数量

        Returns:
            搜索结果列表
        """
        query_vector = await self.embedding_client.embed_single(query)
        results = self.qdrant_store.search(
            paper_id=paper_id,
            query_vector=query_vector,
            limit=limit,
        )
        return results
