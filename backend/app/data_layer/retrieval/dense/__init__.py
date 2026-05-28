"""向量检索模块

从 ChromaDB 执行向量相似度检索。
"""

from .vector_retriever import DenseRetriever, RetrievalDoc

__all__ = ["DenseRetriever", "RetrievalDoc"]
