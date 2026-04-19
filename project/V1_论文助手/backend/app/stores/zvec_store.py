from __future__ import annotations

import os
import shutil

import zvec
from zvec import Doc, VectorQuery


class ZvecStore:
    def __init__(self, path: str, dimension: int = 1536):
        self._path = path
        self._dimension = dimension
        self._collection: zvec.Collection | None = None

    @staticmethod
    def _build_schema(dimension: int) -> zvec.CollectionSchema:
        return zvec.CollectionSchema(
            name="papers",
            fields=[
                zvec.FieldSchema("paper_id", zvec.DataType.STRING),
                zvec.FieldSchema("file_hash", zvec.DataType.STRING),
                zvec.FieldSchema("chunk_type", zvec.DataType.STRING),
                zvec.FieldSchema("chunk_index", zvec.DataType.INT32),
                zvec.FieldSchema("content", zvec.DataType.STRING),
                zvec.FieldSchema("source_page", zvec.DataType.INT32),
                zvec.FieldSchema("section_title", zvec.DataType.STRING),
                zvec.FieldSchema("has_image", zvec.DataType.STRING),
            ],
            vectors=zvec.VectorSchema(
                "embedding", zvec.DataType.VECTOR_FP32, dimension=dimension
            ),
        )

    def init(self) -> None:
        schema = self._build_schema(self._dimension)
        try:
            self._collection = zvec.open(self._path)
        except Exception:
            # create_and_open 要求目标目录不存在
            if os.path.exists(self._path):
                shutil.rmtree(self._path)
            self._collection = zvec.create_and_open(self._path, schema)

    def close(self) -> None:
        if self._collection:
            self._collection.flush()

    def insert_chunks(
        self,
        paper_id: str,
        chunks: list[dict],
        vectors: list[list[float]],
    ) -> int:
        docs = []
        for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
            docs.append(
                Doc(
                    id=f"{paper_id}_{i}",
                    vectors={"embedding": vec},
                    fields={
                        "paper_id": paper_id,
                        "file_hash": chunk.get("file_hash", ""),
                        "chunk_type": chunk.get("chunk_type", "paragraph"),
                        "chunk_index": i,
                        "content": chunk["content"],
                        "source_page": chunk.get("source_page", 0),
                        "section_title": chunk.get("section_title", ""),
                        "has_image": chunk.get("has_image", "false"),
                    },
                )
            )
        self._collection.insert(docs)
        return len(docs)

    def query(
        self,
        vector: list[float],
        topk: int = 10,
        paper_id: str | None = None,
    ) -> list[Doc]:
        kwargs: dict = {
            "vectors": VectorQuery("embedding", vector=vector),
            "topk": topk,
        }
        if paper_id:
            kwargs["filter"] = f"paper_id = '{paper_id}'"
        return self._collection.query(**kwargs)

    def delete_paper(self, paper_id: str) -> None:
        self._collection.delete_by_filter(f"paper_id = '{paper_id}'")

    @property
    def stats(self) -> dict:
        if not self._collection:
            return {"doc_count": 0}
        s = self._collection.stats
        return {"doc_count": s.doc_count}
