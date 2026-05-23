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
    """BM25 关键词索引仓储（支持增量更新）.

    🔴 P1-3 优化：实现增量添加机制，避免每次都全量重建索引
    """

    def __init__(self):
        settings = get_settings()
        self._index_path = Path(settings.bm25_index_path)
        self._corpus: list[str] = []
        self._tokenized: list[list[str]] = []
        self._doc_ids: list[str] = []
        self._bm25: Optional[BM25Okapi] = None

        # 🔴 P1-3 优化：增量更新配置
        self._pending_docs: list[tuple[str, str]] = []  # 待添加文档 (doc_id, document)
        self._rebuild_threshold = 10  # 累积 10 个文档后重建
        self._index_version = 0  # 索引版本号

        # 尝试加载已有索引
        if self._index_path.exists():
            self.load()

    def add(self, doc_id: str, document: str):
        """增量添加单个文档（延迟重建）.

        🔴 P1-3 优化：添加到待处理队列，达到阈值后统一重建索引
        """
        # 检查是否已存在
        if doc_id in self._doc_ids:
            return

        # 添加到待处理队列
        self._pending_docs.append((doc_id, document))

        # 🔴 P1-3 优化：达到阈值后重建索引
        if len(self._pending_docs) >= self._rebuild_threshold:
            self._rebuild_index()

    def _rebuild_index(self):
        """重建 BM25 索引（批量处理待添加文档）.

        🔴 P1-3 优化：批量重建，减少重建次数
        """
        if not self._pending_docs:
            return

        # 合并新旧文档
        for doc_id, document in self._pending_docs:
            self._doc_ids.append(doc_id)
            self._corpus.append(document)
            tokens = list(jieba.cut(document))
            self._tokenized.append(tokens)

        # 清空待处理队列
        self._pending_docs.clear()

        # 重建索引
        if self._tokenized:
            self._bm25 = BM25Okapi(self._tokenized)
            self._index_version += 1  # 🔴 P1-3 优化：更新版本号

    def force_rebuild(self):
        """强制重建索引（立即处理所有待添加文档）.

        🔴 P1-3 优化：用于保存索引前确保所有文档都已索引
        """
        self._rebuild_index()

    def add_batch(self, doc_ids: list[str], documents: list[str]):
        """批量添加文档（增量更新）.

        🔴 P1-3 优化：添加到待处理队列，不会立即重建索引
        """
        if len(doc_ids) != len(documents):
            raise ValueError("doc_ids and documents must have same length")

        # 批量添加到待处理队列
        for doc_id, document in zip(doc_ids, documents):
            if doc_id not in self._doc_ids:
                self._pending_docs.append((doc_id, document))

        # 🔴 P1-3 优化：大批量添加时立即重建
        if len(self._pending_docs) >= self._rebuild_threshold:
            self._rebuild_index()

    def query(self, query_text: str, top_k: int = 30) -> list[tuple[str, float]]:
        """关键词检索（查询前确保索引最新）.

        🔴 P1-3 优化：查询前重建索引，确保能查到待添加的文档

        Returns:
            [(doc_id, score), ...]
        """
        # 🔴 P1-3 优化：查询前重建索引，确保能查到待添加的文档
        self.force_rebuild()

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
        """持久化索引（保存前确保所有文档已索引）.

        🔴 P1-3 优化：保存前强制重建索引，处理所有待添加文档
        """
        # 🔴 P1-3 优化：保存前确保所有待添加文档都已索引
        self.force_rebuild()

        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._index_path, 'wb') as f:
            pickle.dump({
                'corpus': self._corpus,
                'tokenized': self._tokenized,
                'doc_ids': self._doc_ids,
                'version': self._index_version,  # 🔴 P1-3 优化：保存版本号
            }, f)

    def load(self):
        """加载索引（支持版本号）.

        🔴 P1-3 优化：加载版本号，用于索引版本管理
        """
        with open(self._index_path, 'rb') as f:
            data = pickle.load(f)
            self._corpus = data['corpus']
            self._tokenized = data['tokenized']
            self._doc_ids = data['doc_ids']
            # 🔴 P1-3 优化：加载版本号（兼容旧数据）
            self._index_version = data.get('version', 0)
            if self._tokenized:
                self._bm25 = BM25Okapi(self._tokenized)

    def count(self) -> int:
        """获取文档数量"""
        return len(self._doc_ids)

    def get_version(self) -> int:
        """获取索引版本号.

        🔴 P1-3 优化：用于跟踪索引更新
        """
        return self._index_version
