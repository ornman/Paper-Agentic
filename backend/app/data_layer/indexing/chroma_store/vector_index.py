"""Chromadb 向量存储"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

import chromadb

logger = logging.getLogger("paper-assistant")


@dataclass
class Doc:
    """向量检索结果"""
    id: str
    fields: dict = field(default_factory=dict)
    distance: float = 0.0


class VectorIndex:
    def __init__(self, path: str = "./data/chroma_db", dimension: int = 1536):
        self._path = path
        self._dimension = dimension
        self._client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None

    def init(self) -> None:
        os.makedirs(self._path, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=self._path,
            settings=chromadb.Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="papers",
            metadata={"hnsw:space": "cosine", "hnsw:M": 16},
        )
        logger.info("Chroma initialized: %s (%d docs)", self._path, self._collection.count())

    def close(self) -> None:
        self._collection = None
        if self._client is not None:
            try:
                # PersistentClient 没有显式 close，但清除引用帮助 GC
                # 对于某些 chromadb 版本，尝试调用 heartbeat 触发清理
                if hasattr(self._client, "_producer"):
                    self._client._producer = None
                if hasattr(self._client, "_system"):
                    self._client._system = None
            except Exception:
                pass
            self._client = None

    def insert_chunks(
        self,
        paper_id: str,
        chunks: list[dict],
        vectors: list[list[float]],
    ) -> int:
        if not chunks or not vectors:
            return 0

        documents = [c["content"] for c in chunks]
        metadatas = []
        ids = []

        for i, c in enumerate(chunks):
            ids.append(f"{paper_id}_{i}")
            heading_path = c.get("heading_path", "")
            if isinstance(heading_path, list):
                import json as _json
                heading_path = _json.dumps(heading_path, ensure_ascii=False)
            metadatas.append({
                "paper_id": paper_id,
                "file_hash": c.get("file_hash", ""),
                "chunk_type": c.get("chunk_type", "paragraph"),
                "chunk_index": i,
                "source_page": c.get("source_page", 0),
                "section_title": c.get("section_title", ""),
                "has_image": c.get("has_image", "false"),
                "anchor_id": c.get("anchor_id", ""),
                "chunk_id": c.get("chunk_id", ""),
                "heading_path": heading_path,
                "char_start": c.get("char_start", 0),
                "char_end": c.get("char_end", 0),
                "parent_anchor_id": c.get("parent_anchor_id", ""),
                "parent_chunk_id": c.get("parent_chunk_id", ""),
            })

        self._collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=vectors,
            metadatas=metadatas,
        )
        return len(chunks)

    def query(
        self,
        vector: list[float],
        topk: int = 10,
        paper_ids: list[str] | None = None,
    ) -> list[Doc]:
        normalized_paper_ids = [paper_id for paper_id in (paper_ids or []) if paper_id]
        where = None
        if len(normalized_paper_ids) == 1:
            where = {"paper_id": {"$eq": normalized_paper_ids[0]}}
        elif len(normalized_paper_ids) > 1:
            where = {"paper_id": {"$in": normalized_paper_ids}}

        results = self._collection.query(
            query_embeddings=[vector],
            n_results=topk,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        docs = []
        ids = results.get("ids", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i, doc_id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            content = documents[i] if i < len(documents) else ""
            distance = distances[i] if i < len(distances) else 0.0
            fields = dict(meta) if meta else {}
            fields["content"] = content
            # cosine distance: 0 = identical, 2 = opposite
            # 转换为 similarity score: 1 - distance/2
            score = 1.0 - distance / 2.0 if distance <= 2.0 else 0.0
            docs.append(Doc(id=doc_id, fields=fields, distance=distance))

        return docs

    def delete_paper(self, paper_id: str) -> None:
        self._collection.delete(where={"paper_id": {"$eq": paper_id}})

    def rename_paper(self, old_id: str, new_id: str) -> None:
        """将 old_id 前缀的 doc 重命名为 new_id（用于 rebuild 原子替换）"""
        results = self._collection.get(
            where={"paper_id": {"$eq": old_id}},
            include=["documents", "embeddings", "metadatas"],
        )
        old_ids = results.get("ids", [])
        if not old_ids:
            return

        new_ids = [did.replace(f"{old_id}_", f"{new_id}_", 1) for did in old_ids]
        metadatas = results.get("metadatas", [])
        for meta in metadatas:
            if meta:
                meta["paper_id"] = new_id

        self._collection.upsert(
            ids=new_ids,
            documents=results.get("documents", []),
            embeddings=results.get("embeddings", []),
            metadatas=metadatas,
        )
        self._collection.delete(where={"paper_id": {"$eq": old_id}})

    @property
    def stats(self) -> dict:
        if not self._collection:
            return {"doc_count": 0}
        return {"doc_count": self._collection.count()}
