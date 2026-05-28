"""BM25 关键词检索索引"""

from __future__ import annotations

import json
import logging
import os

import jieba
from rank_bm25 import BM25Okapi

logger = logging.getLogger("paper-assistant")


class KeywordIndex:
    def __init__(self, index_dir: str = "./data/bm25_index"):
        self._index_dir = index_dir
        self._corpus: list[list[str]] = []
        self._doc_ids: list[str] = []
        self._bm25: BM25Okapi | None = None
        self._metadata_map: dict[str, dict] = {}  # doc_id -> {"content": str, ...}

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
            metadata_path = os.path.join(self._index_dir, "metadata.json")
            if os.path.exists(metadata_path):
                with open(metadata_path, encoding="utf-8") as f:
                    self._metadata_map = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("BM25 索引损坏，清空重建: %s", e)
            self._corpus = []
            self._doc_ids = []
            self._bm25 = None
            self._metadata_map = {}
            self._save_index()

    def _save_index(self) -> None:
        meta_path = os.path.join(self._index_dir, "meta.json")
        corpus_path = os.path.join(self._index_dir, "corpus.json")
        metadata_path = os.path.join(self._index_dir, "metadata.json")

        meta_tmp = meta_path + ".tmp"
        corpus_tmp = corpus_path + ".tmp"
        metadata_tmp = metadata_path + ".tmp"

        with open(meta_tmp, "w", encoding="utf-8") as f:
            json.dump({"doc_ids": self._doc_ids}, f, ensure_ascii=False)
        with open(corpus_tmp, "w", encoding="utf-8") as f:
            json.dump(self._corpus, f, ensure_ascii=False)
        with open(metadata_tmp, "w", encoding="utf-8") as f:
            json.dump(self._metadata_map, f, ensure_ascii=False)

        os.replace(meta_tmp, meta_path)
        os.replace(corpus_tmp, corpus_path)
        os.replace(metadata_tmp, metadata_path)

    def add_documents(
        self,
        doc_ids: list[str],
        texts: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        tokenized = [list(jieba.cut(text)) for text in texts]
        self._doc_ids.extend(doc_ids)
        self._corpus.extend(tokenized)
        if metadatas:
            for doc_id, meta in zip(doc_ids, metadatas):
                self._metadata_map[doc_id] = meta
        else:
            for doc_id, text in zip(doc_ids, texts):
                self._metadata_map[doc_id] = {"content": text}
        self._bm25 = BM25Okapi(self._corpus)
        self._save_index()

    def get_metadata(self, doc_id: str) -> dict | None:
        """获取文档元数据"""
        return self._metadata_map.get(doc_id)

    def get_contents(self, doc_ids: list[str]) -> dict[str, str]:
        """批量获取文档 content"""
        return {
            doc_id: self._metadata_map.get(doc_id, {}).get("content", "")
            for doc_id in doc_ids
        }

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
        # 返回 topk 结果，不强制过滤 score > 0（小语料库 BM25 分数可能全为 0）
        return scored[:topk]

    def delete_paper(self, paper_id: str) -> None:
        prefix = f"{paper_id}_"
        removed_ids = {did for did in self._doc_ids if did.startswith(prefix)}
        if not removed_ids:
            return
        keep = [(did, corpus) for did, corpus in zip(self._doc_ids, self._corpus)
                if did not in removed_ids]
        self._doc_ids = [did for did, _ in keep]
        self._corpus = [corpus for _, corpus in keep]
        for did in removed_ids:
            self._metadata_map.pop(did, None)
        if self._corpus:
            self._bm25 = BM25Okapi(self._corpus)
        else:
            self._bm25 = None
        self._save_index()

    def rename_paper(self, old_id: str, new_id: str) -> None:
        """将 old_id 前缀的 doc 重命名为 new_id（用于 rebuild 原子替换）"""
        old_prefix = f"{old_id}_"
        new_prefix = f"{new_id}_"
        new_doc_ids = []
        new_metadata_map = {}
        for did in self._doc_ids:
            if did.startswith(old_prefix):
                new_did = new_prefix + did[len(old_prefix):]
                new_doc_ids.append(new_did)
                meta = self._metadata_map.pop(did, {})
                if "paper_id" in meta:
                    meta["paper_id"] = new_id
                new_metadata_map[new_did] = meta
            else:
                new_doc_ids.append(did)
        self._doc_ids = new_doc_ids
        self._metadata_map.update(new_metadata_map)
        self._save_index()

    @property
    def doc_count(self) -> int:
        return len(self._doc_ids)
