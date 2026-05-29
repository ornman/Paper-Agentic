"""向量检索器

从 ChromaDB 执行向量相似度检索。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RetrievalDoc:
    """检索结果文档"""
    id: str
    content: str
    metadata: dict = field(default_factory=dict)
    score: float = 0.0


class DenseRetriever:
    """向量检索器

    从 ChromaDB 执行向量相似度检索。
    """

    def __init__(self, vector_index, max_distance: float = 0):
        """
        Args:
            vector_index: VectorIndex 实例
            max_distance: 距离转分数的最大距离阈值（0 = 从 settings 读取）
        """
        self._vector_index = vector_index
        if max_distance <= 0:
            from app.service_layer.config.settings import get_settings
            max_distance = get_settings().retrieval_max_distance
        self._max_distance = max_distance

    def retrieve(
        self,
        query_vector: list[float],
        topk: int = 0,
        paper_ids: list[str] | None = None,
    ) -> list[RetrievalDoc]:
        """执行向量检索

        Args:
            query_vector: 查询向量
            topk: 返回数量（0 = 从 settings 读取）
            paper_ids: 过滤的论文 ID 列表

        Returns:
            RetrievalDoc 列表
        """
        if not topk:
            from app.service_layer.config.settings import get_settings
            topk = get_settings().retrieval_topk_dense

        docs = self._vector_index.query(
            vector=query_vector,
            topk=topk,
            paper_ids=paper_ids,
        )

        return [
            RetrievalDoc(
                id=doc.id,
                content=doc.fields.get("content", ""),
                metadata={k: v for k, v in doc.fields.items() if k != "content"},
                score=1.0 - doc.distance / self._max_distance if doc.distance <= self._max_distance else 0.0,
            )
            for doc in docs
        ]
