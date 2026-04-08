# Chroma 向量仓储
# 这里封装 Task 5 需要的最小能力：
# 1. 批量写入向量
# 2. 按 document_id 统计数量
# 3. 按 document_id 删除

from __future__ import annotations

from pathlib import Path

import chromadb

from app.core.config import get_settings
from app.modules.indexing.dto import IndexedChunk


class ChromaRepo:
    """最小 Chroma 仓储封装。"""

    def __init__(self) -> None:
        settings = get_settings()
        persist_dir = Path(settings.chroma_persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "l2"},
        )

    def upsert_chunks(self, chunks: list[IndexedChunk], embeddings: list[list[float]]) -> int:
        """批量写入或更新向量块。"""
        if len(chunks) != len(embeddings):
            raise ValueError("chunks 与 embeddings 数量必须一致")
        if not chunks:
            return 0

        self._collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            embeddings=embeddings,
            documents=[chunk.text for chunk in chunks],
            metadatas=[self._build_metadata(chunk) for chunk in chunks],
        )
        return len(chunks)

    def list_ids(self, *, document_id: str) -> list[str]:
        """列出某个文档在向量库中的所有块 ID。"""
        result = self._collection.get(where={"document_id": document_id}, include=["metadatas"])
        return list(result.get("ids") or [])

    def snapshot_document(self, *, document_id: str) -> list[dict[str, object]]:
        """抓取单文档当前向量快照，用于跨仓储补偿恢复。"""
        result = self._collection.get(
            where={"document_id": document_id},
            include=["embeddings", "documents", "metadatas"],
        )
        ids_raw = result.get("ids")
        documents_raw = result.get("documents")
        embeddings_raw = result.get("embeddings")
        metadatas_raw = result.get("metadatas")

        ids = list(ids_raw) if ids_raw is not None else []
        documents = list(documents_raw) if documents_raw is not None else []
        embeddings = list(embeddings_raw) if embeddings_raw is not None else []
        metadatas = list(metadatas_raw) if metadatas_raw is not None else []

        return [
            {
                "id": chunk_id,
                "document": documents[index],
                "embedding": embeddings[index],
                "metadata": metadatas[index],
            }
            for index, chunk_id in enumerate(ids)
        ]

    def restore_document(self, snapshot: list[dict[str, object]]) -> int:
        """把 document 快照重新写回 Chroma。"""
        if not snapshot:
            return 0

        self._collection.upsert(
            ids=[record["id"] for record in snapshot],
            embeddings=[record["embedding"] for record in snapshot],
            documents=[record["document"] for record in snapshot],
            metadatas=[record["metadata"] for record in snapshot],
        )
        return len(snapshot)

    def delete_document(self, document_id: str) -> int:
        """删除某个文档的全部向量块。"""
        chunk_ids = self.list_ids(document_id=document_id)
        if not chunk_ids:
            return 0
        self._collection.delete(ids=chunk_ids)
        return len(chunk_ids)

    def count(self, document_id: str | None = None) -> int:
        """统计向量数量。"""
        if document_id is None:
            return int(self._collection.count())
        return len(self.list_ids(document_id=document_id))

    @staticmethod
    def _build_metadata(chunk: IndexedChunk) -> dict:
        """把块对象压平成 Chroma 可接受的 metadata。"""
        return {
            "document_id": chunk.document_id,
            "node_kind": chunk.node_kind,
            "searchable": chunk.searchable,
            "parent_chunk_id": chunk.parent_chunk_id or "",
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
        }
