"""RAG 检索服务.

完整流程：Query 改写 → 多 Query 并行检索 → RRF 融合 → Rerank.
"""

from __future__ import annotations

from typing import Any

from app.clients.rerank_client import RerankClient
from app.services.embedding_service import EmbeddingService
from app.services.query_rewrite_service import rewrite_query
from app.stores.qdrant_store import QdrantStore
from app.core.config import get_settings

settings = get_settings()


def _reciprocal_rank_fusion(
    *result_lists: list[tuple[str, float]],
    k: int = 60,
) -> list[tuple[str, float]]:
    """RRF 融合算法（支持多路输入）.

    Args:
        *result_lists: 任意数量的结果列表，每个是 [(doc_id, score), ...]
        k: RRF 参数

    Returns:
        融合后的结果列表
    """
    scores: dict[str, float] = {}

    for result_list in result_lists:
        for rank, (doc_id, _) in enumerate(result_list):
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)

    sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results


class RetrievalService:
    """检索服务."""

    def __init__(
        self,
        qdrant_store: QdrantStore | None = None,
        embedding_service: EmbeddingService | None = None,
        rerank_client: RerankClient | None = None,
    ):
        """初始化检索服务.

        Args:
            qdrant_store: Qdrant 存储
            embedding_service: Embedding 服务
            rerank_client: Rerank 客户端
        """
        self.qdrant_store = qdrant_store or QdrantStore()
        self.embedding_service = embedding_service or EmbeddingService()
        self.rerank_client = rerank_client or RerankClient()

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        use_rewrite: bool = True,
    ) -> dict[str, Any]:
        """完整检索流程.

        流程：
        1. Query 改写（1 → 1~3 个检索 query）
        2. 每个 query 做向量检索
        3. 所有结果 RRF 融合
        4. Reranker 重排序
        5. 返回 Top-K

        Args:
            query: 用户查询
            top_k: 最终返回数量
            use_rewrite: 是否启用 query 改写

        Returns:
            {
                "original_query": str,
                "rewritten_queries": [str, ...],
                "results": [Qdrant 结果, ...],
            }
        """
        # 1. Query 改写
        if use_rewrite:
            rewritten_queries = await rewrite_query(query)
        else:
            rewritten_queries = [query]

        print(f"🔍 检索查询: 原始='{query}' → 改写={rewritten_queries}")

        # 2. 多 Query 并行检索
        all_vector_results: list[tuple[str, float]] = []
        all_docs_cache: dict[str, dict] = {}

        for rq in rewritten_queries:
            # 向量检索
            query_embedding = await self.embedding_service.embed_single_async(rq)
            vector_raw = self.qdrant_store.search_all(
                query_vector=query_embedding,
                limit=settings.retrieval_vector_top_k,
            )

            # 缓存结果
            for result in vector_raw:
                doc_id = result["id"]
                if doc_id not in all_docs_cache:
                    all_docs_cache[doc_id] = result

            # 收集结果
            vector_results = [
                (r["id"], r["score"])
                for r in vector_raw
            ]
            all_vector_results.extend(vector_results)

        # 3. RRF 融合
        fused = _reciprocal_rank_fusion(
            all_vector_results,
            k=settings.retrieval_rrf_k,
        )

        if not fused:
            return {
                "original_query": query,
                "rewritten_queries": rewritten_queries,
                "results": [],
            }

        # 4. 准备 Rerank 候选
        candidate_ids = []
        candidate_docs = []

        for doc_id, _ in fused[:30]:
            if doc_id in all_docs_cache:
                result = all_docs_cache[doc_id]
                content = result["payload"].get("content", "")
                candidate_ids.append(doc_id)
                candidate_docs.append(content)

        if not candidate_docs:
            return {
                "original_query": query,
                "rewritten_queries": rewritten_queries,
                "results": [],
            }

        # 5. Rerank（用原始 query）
        reranked = await self.rerank_client.rerank(query, candidate_docs, top_k=top_k)

        # 6. 组装结果
        results = []
        for idx, score in reranked:
            doc_id = candidate_ids[idx]
            results.append(all_docs_cache[doc_id])

        return {
            "original_query": query,
            "rewritten_queries": rewritten_queries,
            "results": results,
        }


# 便捷函数（保持向后兼容）
async def retrieve(
    query: str,
    context: Any = None,
    top_k: int = 10,
    use_rewrite: bool = True,
) -> dict[str, Any]:
    """便捷函数：检索.

    Args:
        query: 用户查询
        context: 上下文（暂未使用）
        top_k: 最终返回数量
        use_rewrite: 是否启用 query 改写

    Returns:
        检索结果
    """
    service = RetrievalService()
    return await service.retrieve(query, top_k, use_rewrite)
