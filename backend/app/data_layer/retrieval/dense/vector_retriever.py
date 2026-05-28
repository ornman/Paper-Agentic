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

    def __init__(self, vector_index):
        """
        Args:
            vector_index: VectorIndex 实例
        """
        self._vector_index = vector_index

    def retrieve(
        self,
        query_vector: list[float],
        topk: int = 10,
        paper_ids: list[str] | None = None,
    ) -> list[RetrievalDoc]:
        """执行向量检索

        Args:
            query_vector: 查询向量
            topk: 返回数量
            paper_ids: 过滤的论文 ID 列表

        Returns:
            RetrievalDoc 列表
        """
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
                score=1.0 - doc.distance / 2.0 if doc.distance <= 2.0 else 0.0,
            )
            for doc in docs
        ]
