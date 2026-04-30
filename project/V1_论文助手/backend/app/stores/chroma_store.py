"""Chromadb 向量存储（替代 zvec，根治锁问题）"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

import chromadb

logger = logging.getLogger("paper-assistant")


@dataclass
class Doc:
    """兼容 zvec.Doc 的数据类"""
    id: str
    fields: dict = field(default_factory=dict)


class ChromaStore:
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
            metadatas.append({
                "paper_id": paper_id,
                "file_hash": c.get("file_hash", ""),
                "chunk_type": c.get("chunk_type", "paragraph"),
                "chunk_index": i,
                "source_page": c.get("source_page", 0),
                "section_title": c.get("section_title", ""),
                "has_image": c.get("has_image", "false"),
            })

        # chromadb upsert 支持幂等写入
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
            include=["documents", "metadatas"],
        )

        docs = []
        ids = results.get("ids", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        documents = results.get("documents", [[]])[0]

        for i, doc_id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            content = documents[i] if i < len(documents) else ""
            fields = dict(meta) if meta else {}
            fields["content"] = content
            docs.append(Doc(id=doc_id, fields=fields))

        return docs

    def delete_paper(self, paper_id: str) -> None:
        self._collection.delete(where={"paper_id": {"$eq": paper_id}})

    @property
    def stats(self) -> dict:
        if not self._collection:
            return {"doc_count": 0}
        return {"doc_count": self._collection.count()}
