# ChromaDB 仓储层
# 管理向量索引的增删查
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import Optional
from app.core.config import get_settings
from pathlib import Path


class ChromaRepo:
    """ChromaDB 向量库仓储"""

    def __init__(self):
        settings = get_settings()
        persist_dir = Path(settings.chroma_persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "l2"}
        )

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: Optional[list[dict]] = None,
    ):
        """批量添加向量"""
        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 30,
        where: Optional[dict] = None,
    ) -> dict:
        """向量检索"""
        return self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

    def delete_by_ids(self, ids: list[str]):
        """按 ID 删除"""
        self._collection.delete(ids=ids)

    def delete_by_document(self, document_id: str):
        """按文档 ID 删除（metadata.document_id）"""
        self._collection.delete(
            where={"document_id": document_id}
        )

    def count(self) -> int:
        """获取向量数量"""
        return self._collection.count()

    def clear(self):
        """清空集合"""
        settings = get_settings()
        self._client.delete_collection(settings.chroma_collection_name)
        self._collection = self._client.create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "l2"}
        )
