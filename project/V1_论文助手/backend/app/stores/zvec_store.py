from __future__ import annotations

import atexit
import logging
import os
import time

import zvec
from zvec import Doc, VectorQuery

logger = logging.getLogger("paper-assistant")


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

        # 路径不存在 → 全新创建
        if not os.path.exists(self._path):
            self._collection = zvec.create_and_open(self._path, schema)
            logger.info("Zvec 新建: %s", self._path)
            self._register_atexit()
            return

        # 尝试正常打开
        col = self._try_open_with_lock_recovery()
        if col is not None:
            self._collection = col
            self._register_atexit()
            return

        # 所有尝试都失败 → 创建新库（只在目录为空时）
        if self._is_data_dir_empty():
            logger.warning("Zvec 目录为空，重新创建: %s", self._path)
            self._collection = zvec.create_and_open(self._path, schema)
            self._register_atexit()
            return

        # 目录有数据但打不开 → 致命错误，不删数据
        raise RuntimeError(
            f"Zvec 数据目录存在但无法打开 ({self._path})。"
            "请手动删除 data/zvec_db/ 下所有 LOCK 文件后重启。"
            "不要删除整个目录，否则向量数据会丢失！"
        )

    def _try_open_with_lock_recovery(self, max_retries: int = 3) -> zvec.Collection | None:
        """尝试打开 zvec，遇到 LOCK 问题时自动清理并重试"""
        for attempt in range(max_retries):
            try:
                return zvec.open(self._path)
            except RuntimeError as e:
                err_msg = str(e).lower()
                if "lock" not in err_msg:
                    logger.error("Zvec 打开失败（非 LOCK 错误）: %s", e)
                    return None

                logger.warning(
                    "Zvec LOCK 冲突 (尝试 %d/%d): %s",
                    attempt + 1, max_retries, e,
                )
                self._remove_lock_files()

                # Windows 上文件句柄释放需要时间，等待后重试
                if attempt < max_retries - 1:
                    time.sleep(1.0)
            except Exception as e:
                logger.error("Zvec 打开失败: %s", e)
                return None

        # LOCK 清理后仍然打开失败
        logger.error("Zvec LOCK 清理后仍无法打开，重试 %d 次均失败", max_retries)
        return None

    def _is_data_dir_empty(self) -> bool:
        """检查数据目录是否只有 LOCK 文件（没有实际数据）"""
        has_data = False
        for root, _dirs, files in os.walk(self._path):
            for f in files:
                if f != "LOCK":
                    has_data = True
                    break
            if has_data:
                break
        return not has_data

    def _remove_lock_files(self) -> None:
        """清理所有残留 LOCK 文件"""
        for root, _dirs, files in os.walk(self._path):
            for f in files:
                if f == "LOCK":
                    lock_path = os.path.join(root, f)
                    try:
                        os.remove(lock_path)
                        logger.warning("清理残留 LOCK: %s", lock_path)
                    except OSError as e:
                        logger.warning("无法删除 LOCK (%s): %s", lock_path, e)

    def close(self) -> None:
        if self._collection:
            try:
                self._collection.flush()
            except Exception as e:
                logger.warning("Zvec flush 失败: %s", e)
            # 释放底层 C++ 句柄，让 RocksDB 正常释放 LOCK
            try:
                self._collection = None
            except Exception:
                pass

    def _register_atexit(self) -> None:
        """注册 atexit 钩子，确保进程退出时释放 LOCK"""
        collection = self._collection

        def _cleanup():
            if collection is not None:
                try:
                    collection.flush()
                except Exception:
                    pass

        atexit.register(_cleanup)

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
