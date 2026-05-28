"""软删除管理器

管理 ChromaDB 和 BM25 索引的软删除策略。
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("paper-assistant")


@dataclass
class SoftDeleteRecord:
    """软删除记录"""
    paper_id: str
    deleted_at: float  # timestamp
    chroma_deleted: bool = False
    bm25_deleted: bool = False


class SoftDeleteManager:
    """软删除管理器

    删除时标记 deleted_at，启动时检查超过保留期的记录真正删除。
    """

    def __init__(
        self,
        index_dir: str,
        retention_days: int = 7,
    ):
        self._index_dir = Path(index_dir)
        self._retention_days = retention_days
        self._records_file = self._index_dir / "soft_delete_records.json"
        self._records: dict[str, SoftDeleteRecord] = {}

    def init(self):
        """初始化，加载软删除记录"""
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._load_records()

    def mark_deleted(self, paper_id: str):
        """标记为软删除

        Args:
            paper_id: 论文 ID
        """
        self._records[paper_id] = SoftDeleteRecord(
            paper_id=paper_id,
            deleted_at=time.time(),
        )
        self._save_records()
        logger.info("标记软删除: %s", paper_id)

    def cleanup_expired(
        self,
        vector_index=None,
        keyword_index=None,
    ) -> list[str]:
        """清理过期的软删除记录

        Args:
            vector_index: 向量索引实例
            keyword_index: 关键词索引实例

        Returns:
            已清理的 paper_id 列表
        """
        now = time.time()
        retention_seconds = self._retention_days * 24 * 3600
        cleaned = []

        for paper_id, record in list(self._records.items()):
            if now - record.deleted_at > retention_seconds:
                # 超过保留期，真正删除
                if vector_index and not record.chroma_deleted:
                    try:
                        vector_index.delete_paper(paper_id)
                        record.chroma_deleted = True
                    except Exception as e:
                        logger.warning("向量索引删除失败: %s, %s", paper_id, e)

                if keyword_index and not record.bm25_deleted:
                    try:
                        keyword_index.delete_paper(paper_id)
                        record.bm25_deleted = True
                    except Exception as e:
                        logger.warning("关键词索引删除失败: %s, %s", paper_id, e)

                if record.chroma_deleted and record.bm25_deleted:
                    del self._records[paper_id]
                    cleaned.append(paper_id)
                    logger.info("已清理过期软删除: %s", paper_id)

        if cleaned:
            self._save_records()

        return cleaned

    def is_deleted(self, paper_id: str) -> bool:
        """检查是否已软删除"""
        return paper_id in self._records

    def get_records(self) -> dict[str, SoftDeleteRecord]:
        """获取所有软删除记录"""
        return self._records.copy()

    def _load_records(self):
        """加载软删除记录"""
        if not self._records_file.exists():
            return

        try:
            with open(self._records_file, encoding="utf-8") as f:
                data = json.load(f)

            for paper_id, record_data in data.items():
                self._records[paper_id] = SoftDeleteRecord(
                    paper_id=paper_id,
                    deleted_at=record_data.get("deleted_at", 0),
                    chroma_deleted=record_data.get("chroma_deleted", False),
                    bm25_deleted=record_data.get("bm25_deleted", False),
                )

        except (json.JSONDecodeError, IOError) as e:
            logger.warning("软删除记录加载失败: %s", e)

    def _save_records(self):
        """保存软删除记录"""
        data = {
            paper_id: {
                "deleted_at": record.deleted_at,
                "chroma_deleted": record.chroma_deleted,
                "bm25_deleted": record.bm25_deleted,
            }
            for paper_id, record in self._records.items()
        }

        tmp_path = self._records_file.with_suffix(self._records_file.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        os.replace(tmp_path, self._records_file)
