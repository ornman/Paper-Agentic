from __future__ import annotations

import json
import logging
import math
import os
from collections import defaultdict

import jieba
from rank_bm25 import BM25Okapi

logger = logging.getLogger("paper-assistant")


class BM25Store:
    """BM25 关键词检索索引（P5 三层检索时完善）"""

    def __init__(self, index_dir: str = "./data/bm25_index"):
        self._index_dir = index_dir
        self._corpus: list[list[str]] = []
        self._doc_ids: list[str] = []
        self._bm25: BM25Okapi | None = None

    def init(self) -> None:
        os.makedirs(self._index_dir, exist_ok=True)
        self._load_index()

    def _load_index(self) -> None:
        meta_path = os.path.join(self._index_dir, "meta.json")
        if not os.path.exists(meta_path):
            return
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            self._doc_ids = meta.get("doc_ids", [])
            corpus_path = os.path.join(self._index_dir, "corpus.json")
            if os.path.exists(corpus_path):
                with open(corpus_path, encoding="utf-8") as f:
                    self._corpus = json.load(f)
                if self._corpus:
                    self._bm25 = BM25Okapi(self._corpus)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("BM25 索引损坏，清空重建: %s", e)
            self._corpus = []
            self._doc_ids = []
            self._bm25 = None
            self._save_index()

    def _save_index(self) -> None:
        meta_path = os.path.join(self._index_dir, "meta.json")
        corpus_path = os.path.join(self._index_dir, "corpus.json")

        # 原子写入：先写临时文件，完成后重命名
        meta_tmp = meta_path + ".tmp"
        corpus_tmp = corpus_path + ".tmp"

        with open(meta_tmp, "w", encoding="utf-8") as f:
            json.dump({"doc_ids": self._doc_ids}, f, ensure_ascii=False)
        with open(corpus_tmp, "w", encoding="utf-8") as f:
            json.dump(self._corpus, f, ensure_ascii=False)

        os.replace(meta_tmp, meta_path)
        os.replace(corpus_tmp, corpus_path)

    def add_documents(self, doc_ids: list[str], texts: list[str]) -> None:
        tokenized = [list(jieba.cut(text)) for text in texts]
        self._doc_ids.extend(doc_ids)
        self._corpus.extend(tokenized)
        self._bm25 = BM25Okapi(self._corpus)
        self._save_index()

    def query(self, query_text: str, topk: int = 10, paper_ids: list[str] | None = None) -> list[tuple[str, float]]:
        if not self._bm25:
            return []

        allowed_paper_ids = {paper_id for paper_id in (paper_ids or []) if paper_id}
        tokens = list(jieba.cut(query_text))
        scores = self._bm25.get_scores(tokens)
        scored = list(zip(self._doc_ids, scores))

        if allowed_paper_ids:
            scored = [
                (doc_id, score)
                for doc_id, score in scored
                if doc_id.split("_", 1)[0] in allowed_paper_ids
            ]

        scored.sort(key=lambda x: x[1], reverse=True)
        return [(did, s) for did, s in scored[:topk] if s > 0]

    def delete_paper(self, paper_id: str) -> None:
        keep = [(did, corpus) for did, corpus in zip(self._doc_ids, self._corpus)
                if not did.startswith(f"{paper_id}_")]
        if len(keep) == len(self._doc_ids):
            return
        self._doc_ids = [did for did, _ in keep]
        self._corpus = [corpus for _, corpus in keep]
        if self._corpus:
            self._bm25 = BM25Okapi(self._corpus)
        else:
            self._bm25 = None
        self._save_index()

    @property
    def doc_count(self) -> int:
        return len(self._doc_ids)
