"""RRF 融合检索"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FusedDoc:
    """融合结果文档"""
    id: str
    content: str
    metadata: dict = field(default_factory=dict)
    score: float = 0.0
    dense_rank: int = 0
    sparse_rank: int = 0


def rrf_fuse(
    dense_results: list,
    sparse_results: list,
    topk: int = 0,
    keyword_index=None,
    rrf_k: int = 60,
) -> list[FusedDoc]:
    """RRF 融合 Dense + Sparse 检索结果，返回融合后 topk 的 FusedDoc 列表

    Args:
        dense_results: 向量检索返回，list[Doc/RetrievalDoc]
        sparse_results: BM25 返回，list[SparseResult] 或 list[tuple[str, float]]
        topk: 返回数量
        keyword_index: KeywordIndex 实例（可选，用于 sparse-only 结果获取真实 content）

    Returns:
        FusedDoc 列表（dense+sparse 并集）
    """
    # Dense rank 映射: doc_id -> (rank, doc)
    dense_map: dict[str, tuple[int, object]] = {}
    for rank, doc in enumerate(dense_results, start=1):
        doc_id = doc.id if hasattr(doc, "id") else str(rank)
        dense_map[doc_id] = (rank, doc)

    # Sparse rank 映射: doc_id -> (rank, score)
    # 兼容 SparseResult dataclass 和 tuple 两种格式
    sparse_map: dict[str, tuple[int, float]] = {}
    for rank, item in enumerate(sparse_results, start=1):
        if hasattr(item, "doc_id"):
            # SparseResult dataclass
            sparse_map[item.doc_id] = (rank, item.score)
        elif isinstance(item, (tuple, list)) and len(item) >= 2:
            # (doc_id, score) tuple
            sparse_map[item[0]] = (rank, item[1])
        else:
            continue

    # 收集所有 doc_id（dense + sparse 并集）
    all_doc_ids = set(dense_map.keys()) | set(sparse_map.keys())

    # 计算融合分数
    fused_scores: dict[str, float] = {}
    for doc_id in all_doc_ids:
        score = 0.0
        if doc_id in dense_map:
            score += 1.0 / (rrf_k + dense_map[doc_id][0])
        if doc_id in sparse_map:
            score += 1.0 / (rrf_k + sparse_map[doc_id][0])
        fused_scores[doc_id] = score

    # 按融合分数排序
    sorted_ids = sorted(fused_scores, key=lambda x: fused_scores[x], reverse=True)

    results = []
    for doc_id in (sorted_ids if topk <= 0 else sorted_ids[:topk]):
        dense_rank = dense_map[doc_id][0] if doc_id in dense_map else 0
        sparse_rank = sparse_map[doc_id][0] if doc_id in sparse_map else 0

        # 优先使用 dense 的 doc 对象，fallback 到构造 FusedDoc
        if doc_id in dense_map:
            doc = dense_map[doc_id][1]
            content = ""
            metadata = {}
            if hasattr(doc, "fields"):
                content = doc.fields.get("content", "")
                metadata = {k: v for k, v in doc.fields.items() if k != "content"}
            elif hasattr(doc, "content"):
                content = doc.content
                metadata = getattr(doc, "metadata", {})

            results.append(FusedDoc(
                id=doc_id,
                content=content,
                metadata=metadata,
                score=fused_scores[doc_id],
                dense_rank=dense_rank,
                sparse_rank=sparse_rank,
            ))
        else:
            # sparse-only: 从 keyword_index 获取真实 content
            content = ""
            meta = {"source": "bm25_only"}
            if keyword_index is not None:
                stored = keyword_index.get_metadata(doc_id)
                if stored:
                    content = stored.get("content", "")
                    meta = {k: v for k, v in stored.items() if k != "content"}
                    meta["source"] = "bm25_only"
            results.append(FusedDoc(
                id=doc_id,
                content=content,
                metadata=meta,
                score=fused_scores[doc_id],
                dense_rank=0,
                sparse_rank=sparse_rank,
            ))

    return results
