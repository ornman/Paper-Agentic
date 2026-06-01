"""BM25 关键词检索器

从 BM25 索引执行关键词检索。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SparseResult:
    """稀疏检索结果"""
    doc_id: str
    score: float


class SparseRetriever:
    """BM25 关键词检索器

    从 BM25 索引执行关键词检索。
    """

    def __init__(self, keyword_index):
        """
        Args:
            keyword_index: KeywordIndex 实例
        """
        self._keyword_index = keyword_index

    def retrieve(
        self,
        query_text: str,
        topk: int = 0,
        paper_ids: list[str] | None = None,
    ) -> list[SparseResult]:
        """执行关键词检索

        Args:
            query_text: 查询文本
            topk: 返回数量（0 = 从 settings 读取）
            paper_ids: 过滤的论文 ID 列表

        Returns:
            SparseResult 列表
        """
        if not topk:
            from app.service_layer.config.settings import get_settings
            topk = get_settings().retrieval_topk_sparse
        results = self._keyword_index.query(
            query_text=query_text,
            topk=topk,
            paper_ids=paper_ids,
        )

        return [
            SparseResult(doc_id=doc_id, score=score)
            for doc_id, score in results
        ]
