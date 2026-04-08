# BM25 仓储层
# 管理关键词索引的增删查
import json
import pickle
from pathlib import Path
from typing import Optional
from rank_bm25 import BM25Okapi
import jieba
from app.core.config import get_settings


class BM25Repo:
    """BM25 关键词索引仓储"""

    def __init__(self):
        settings = get_settings()
        self._index_path = Path(settings.bm25_index_path)
        self._corpus: list[str] = []
        self._tokenized: list[list[str]] = []
        self._doc_ids: list[str] = []
        self._bm25: Optional[BM25Okapi] = None

        # 尝试加载已有索引
        if self._index_path.exists():
            self.load()

    def add(self, doc_id: str, document: str):
        """添加单个文档"""
        self._doc_ids.append(doc_id)
        self._corpus.append(document)
        tokens = list(jieba.cut(document))
        self._tokenized.append(tokens)
        # 重新构建索引
        self._bm25 = BM25Okapi(self._tokenized)

    def add_batch(self, doc_ids: list[str], documents: list[str]):
        """批量添加文档"""
        self._doc_ids.extend(doc_ids)
        self._corpus.extend(documents)
        for doc in documents:
            tokens = list(jieba.cut(doc))
            self._tokenized.append(tokens)
        # 重新构建索引
        self._bm25 = BM25Okapi(self._tokenized)

    def query(self, query_text: str, top_k: int = 30) -> list[tuple[str, float]]:
        """
        关键词检索

        Returns:
            [(doc_id, score), ...]
        """
        if not self._bm25:
            return []

        query_tokens = list(jieba.cut(query_text))
        scores = self._bm25.get_scores(query_tokens)

        # 获取 Top-K
        import numpy as np
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = [
            (self._doc_ids[i], float(scores[i]))
            for i in top_indices
            if scores[i] > 0
        ]
        return results

    def delete_by_id(self, doc_id: str):
        """删除单个文档"""
        if doc_id not in self._doc_ids:
            return
        idx = self._doc_ids.index(doc_id)
        self._doc_ids.pop(idx)
        self._corpus.pop(idx)
        self._tokenized.pop(idx)
        # 重建索引
        if self._tokenized:
            self._bm25 = BM25Okapi(self._tokenized)
        else:
            self._bm25 = None

    def clear(self):
        """清空索引"""
        self._corpus = []
        self._tokenized = []
        self._doc_ids = []
        self._bm25 = None

    def save(self):
        """持久化索引"""
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._index_path, 'wb') as f:
            pickle.dump({
                'corpus': self._corpus,
                'tokenized': self._tokenized,
                'doc_ids': self._doc_ids,
            }, f)

    def load(self):
        """加载索引"""
        with open(self._index_path, 'rb') as f:
            data = pickle.load(f)
            self._corpus = data['corpus']
            self._tokenized = data['tokenized']
            self._doc_ids = data['doc_ids']
            if self._tokenized:
                self._bm25 = BM25Okapi(self._tokenized)

    def count(self) -> int:
        """获取文档数量"""
        return len(self._doc_ids)
