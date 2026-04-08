# RAG 检索服务
# 完整流程：Query 改写 → 多 Query 并行检索 → RRF 融合 → Rerank
#
# 改写后可能产出 1-3 个检索 query，每个 query 分别走向量+BM25，
# 所有结果汇总后做一次 RRF 融合 + Rerank。

from typing import List, Optional
from app.repositories.chroma_repo import ChromaRepo
from app.repositories.bm25_repo import BM25Repo
from app.clients.embedding_client import EmbeddingClient
from app.clients.rerank_client import RerankClient
from app.services.query_rewrite_service import QueryRewriteService
from app.models.query import QueryContext
from app.core.config import get_settings


def reciprocal_rank_fusion(
    *result_lists: List[tuple[str, float]],
    k: int = 60,
) -> list[tuple[str, float]]:
    """
    RRF 融合算法（支持多路输入）

    接受任意数量的结果列表，每个列表是 [(doc_id, score), ...]。
    按 RRF 公式合并分数：RRF_score = sum(1 / (k + rank))
    """
    scores: dict[str, float] = {}

    for result_list in result_lists:
        for rank, (doc_id, _) in enumerate(result_list):
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)

    sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results


async def retrieve(
    query: str,
    context: Optional[QueryContext] = None,
    top_k: int = 10,
    use_rewrite: bool = True,
) -> dict:
    """
    完整检索流程

    流程：
    1. Query 改写（1 → 1~3 个检索 query）
    2. 每个 query 做向量检索 + BM25 检索
    3. 所有结果 RRF 融合
    4. Reranker 重排序（用原始 query 做 rerank）
    5. 返回 Top-K

    Args:
        query: 用户原始查询
        context: 上下文（已写内容、圈选文本、prompt）
        top_k: 最终返回数量
        use_rewrite: 是否启用 query 改写

    Returns:
        {
            "original_query": str,
            "rewritten_queries": [str, ...],
            "results": [{"id", "content", "document", "page", "score"}, ...],
        }
    """
    settings = get_settings()
    embedding_client = EmbeddingClient()
    chroma_repo = ChromaRepo()
    bm25_repo = BM25Repo()

    # ============================================================
    # 1. Query 改写
    # ============================================================
    if use_rewrite:
        rewrite_service = QueryRewriteService()
        rewritten_queries = await rewrite_service.rewrite(query, context)
    else:
        rewritten_queries = [query]

    print(f"🔍 检索查询: 原始='{query}' → 改写={rewritten_queries}")

    # ============================================================
    # 2. 多 Query 并行检索
    # ============================================================
    all_vector_results: list[tuple[str, float]] = []
    all_bm25_results: list[tuple[str, float]] = []
    # 缓存所有 ChromaDB 返回的原始数据，后面取原文用
    all_docs_cache: dict[str, tuple[str, dict]] = {}  # doc_id → (content, metadata)

    for rq in rewritten_queries:
        # 向量检索
        query_embedding = await embedding_client.embed_single(rq)
        vector_raw = chroma_repo.query(
            query_embedding,
            top_k=settings.retrieval_vector_top_k,
        )

        # 缓存原文和元数据
        for doc_id, doc_text, meta in zip(
            vector_raw["ids"][0],
            vector_raw["documents"][0],
            vector_raw["metadatas"][0],
        ):
            if doc_id not in all_docs_cache:
                all_docs_cache[doc_id] = (doc_text, meta)

        # 距离转分数
        vector_results = [
            (doc_id, 1.0 / (dist + 1e-6))
            for doc_id, dist in zip(
                vector_raw["ids"][0], vector_raw["distances"][0]
            )
        ]
        all_vector_results.extend(vector_results)

        # BM25 检索
        bm25_results = bm25_repo.query(
            rq, top_k=settings.retrieval_bm25_top_k
        )
        all_bm25_results.extend(bm25_results)

    # ============================================================
    # 3. RRF 融合
    # ============================================================
    fused = reciprocal_rank_fusion(
        all_vector_results,
        all_bm25_results,
        k=settings.retrieval_rrf_k,
    )

    if not fused:
        return {
            "original_query": query,
            "rewritten_queries": rewritten_queries,
            "results": [],
        }

    # ============================================================
    # 4. 准备 Rerank 候选
    # ============================================================
    # 取融合后 Top-30，如果 doc_id 不在缓存里就跳过
    candidate_ids = []
    candidate_docs = []
    candidate_metas = []

    for doc_id, _ in fused[:30]:
        if doc_id in all_docs_cache:
            content, meta = all_docs_cache[doc_id]
            candidate_ids.append(doc_id)
            candidate_docs.append(content)
            candidate_metas.append(meta)

    if not candidate_docs:
        return {
            "original_query": query,
            "rewritten_queries": rewritten_queries,
            "results": [],
        }

    # ============================================================
    # 5. Rerank（用原始 query，因为 rerank 需要和用户意图对齐）
    # ============================================================
    rerank_client = RerankClient()
    reranked = await rerank_client.rerank(query, candidate_docs, top_k=top_k)

    # ============================================================
    # 6. 组装结果
    # ============================================================
    results = []
    for idx, score in reranked:
        meta = candidate_metas[idx]
        results.append({
            "id": candidate_ids[idx],
            "content": candidate_docs[idx],
            "document": meta.get("document", ""),
            "page": meta.get("page"),
            "score": score,
        })

    return {
        "original_query": query,
        "rewritten_queries": rewritten_queries,
        "results": results,
    }
