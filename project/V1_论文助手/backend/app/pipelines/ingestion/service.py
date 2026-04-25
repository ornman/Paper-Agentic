"""导入管道服务：编排 MinerU → VLM图片描述 → 清洗 → 切块 → Embedding → 存储"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from dataclasses import asdict
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy import text

from app.api.v1.deps import get_bm25, get_chroma, get_sqlite
from app.clients.embedding_client import EmbeddingClient
from app.clients.mineru_client import MinerUClient
from app.clients.vlm_client import VLMClient
from app.core.config import get_settings
from app.core.errors import AppError, ImportFailedError
from app.pipelines.ingestion.backup_manager import BackupManager
from app.pipelines.ingestion.chunker import chunk_text
from app.pipelines.ingestion.cleaner import Chunk, clean_markdown
from app.pipelines.ingestion.image_handler import inject_image_descriptions

logger = logging.getLogger("paper-assistant")

_backup = BackupManager()

_BACKUP_STAGE_BY_STATUS = {
    "parsing": "mineru",
    "vlm": "vlm",
    "cleaning": "cleaning",
    "chunking": "chunking",
    "embedding": "embedding",
    "storing": "chroma",
}

_STAGE_LABELS = {
    "parsing": "MinerU 解析",
    "vlm": "VLM 图片理解",
    "cleaning": "数据清洗",
    "chunking": "切块",
    "embedding": "向量化",
    "storing": "写入存储",
}


def _serialize_chunks(chunks: list[Chunk]) -> list[dict]:
    return [asdict(chunk) for chunk in chunks]


class IngestionService:
    def __init__(self):
        self._mineru = MinerUClient()
        self._vlm = VLMClient()
        self._embedding = EmbeddingClient()

    @staticmethod
    def _set_stage_status(
        file_hash: str,
        task_id: str,
        file_path: str,
        status: str,
        step: str,
        backup_stage: str,
        backup_status: str,
        *,
        paper_id: str | None = None,
        error_msg: str | None = None,
        extra: dict | None = None,
    ) -> None:
        IngestionService._log(task_id, file_path, status, step, paper_id=paper_id, error_msg=error_msg)
        _backup.update_stage(
            file_hash,
            backup_stage,
            backup_status,
            extra=extra,
            task_id=task_id,
            error_msg=error_msg,
        )

    @staticmethod
    def _wrap_stage_error(status: str, exc: Exception) -> ImportFailedError:
        if isinstance(exc, ImportFailedError):
            return exc
        label = _STAGE_LABELS.get(status, status)
        return ImportFailedError(f"{label}失败：{exc}", stage=status)

    async def ingest_pdf(
        self,
        file_path: str,
        task_id: str | None = None,
        progress_callback=None,
    ) -> dict:
        if not task_id:
            task_id = uuid.uuid4().hex[:12]

        file_hash = _hash_file(file_path)
        import_time = datetime.now(timezone.utc).isoformat()
        # 去重
        sqlite = get_sqlite()
        with sqlite.get_session() as session:
            result = session.execute(
                text("SELECT paper_id FROM papers WHERE file_hash = :hash"),
                {"hash": file_hash},
            )
            if result.fetchone():
                raise ValueError(f"该论文已导入 (hash: {file_hash[:8]})")

        # 检查备份，支持断点续传
        backup = _backup.get_backup(file_hash)
        if backup and backup["status"] == "completed":
            raise ValueError(f"该论文已完成导入 (hash: {file_hash[:8]})")

        resume_stage = _backup.get_resume_stage(file_hash) if backup else None
        if resume_stage:
            paper_id = backup["paper_id"]
            logger.info("从阶段 %s 恢复导入: %s", resume_stage, file_hash[:12])
        else:
            paper_id = uuid.uuid4().hex[:16]
            _backup.create(file_hash, file_path, paper_id, task_id=task_id)

        # ── Stage 1: MinerU 解析 ──
        md_content = ""
        paper_dir = ""
        images_dir = ""

        if _backup.get_backup(file_hash)["stages"].get("mineru") != "completed":
            self._set_stage_status(
                file_hash,
                task_id,
                file_path,
                "parsing",
                "MinerU 解析中",
                "mineru",
                "running",
                paper_id=paper_id,
            )
            if progress_callback:
                await progress_callback("parsing", "正在提交 PDF 解析...")

            try:
                mineru_result = await self._mineru.run(file_path)
                md_content = mineru_result.md_content or ""
                paper_dir = mineru_result.paper_dir
                images_dir = os.path.join(paper_dir, "images")

                _backup.save_stage_data(file_hash, "mineru", md_content)
                self._set_stage_status(
                    file_hash,
                    task_id,
                    file_path,
                    "parsing",
                    "MinerU 解析完成",
                    "mineru",
                    "completed",
                    paper_id=paper_id,
                )
            except Exception as e:
                stage_error = self._wrap_stage_error("parsing", e)
                self._set_stage_status(
                    file_hash,
                    task_id,
                    file_path,
                    "error",
                    "MinerU 解析失败",
                    "mineru",
                    "failed",
                    paper_id=paper_id,
                    error_msg=stage_error.detail["message"],
                )
                raise stage_error from e
        else:
            md_content = _backup.load_stage_data(file_hash, "mineru") or ""
            logger.info("跳过已完成阶段: mineru")

        # ── Stage 2: VLM 图片描述注入（可降级） ──
        vlm_stage = _backup.get_backup(file_hash)["stages"].get("vlm")
        if vlm_stage not in ("completed", "skipped"):
            self._set_stage_status(
                file_hash,
                task_id,
                file_path,
                "vlm",
                "图片理解中",
                "vlm",
                "running",
                paper_id=paper_id,
            )
            if progress_callback:
                await progress_callback("vlm", "正在处理图片...")

            try:
                if not paper_dir:
                    paper_dir = str(Path(get_settings().papers_dir) / task_id)
                    images_dir = os.path.join(paper_dir, "images")

                if md_content and os.path.isdir(images_dir):
                    md_content = await inject_image_descriptions(
                        md_content, images_dir, paper_dir, self._vlm,
                        concurrency=10, on_error="default",
                    )

                _backup.save_stage_data(file_hash, "vlm", md_content)
                self._set_stage_status(
                    file_hash,
                    task_id,
                    file_path,
                    "vlm",
                    "图片理解完成",
                    "vlm",
                    "completed",
                    paper_id=paper_id,
                )
            except Exception as e:
                logger.warning("VLM 阶段整体失败，降级跳过: %s", e)
                self._set_stage_status(
                    file_hash,
                    task_id,
                    file_path,
                    "vlm",
                    "图片理解跳过",
                    "vlm",
                    "skipped",
                    paper_id=paper_id,
                    error_msg=str(e),
                )
        else:
            md_content = _backup.load_stage_data(file_hash, "vlm") or ""
            logger.info("跳过已完成阶段: vlm")

        # ── Stage 3: 清洗 ──
        cleaning_stage = _backup.get_backup(file_hash)["stages"].get("cleaning")
        if cleaning_stage != "completed":
            self._set_stage_status(
                file_hash,
                task_id,
                file_path,
                "cleaning",
                "数据清洗中",
                "cleaning",
                "running",
                paper_id=paper_id,
            )
            if progress_callback:
                await progress_callback("cleaning", "正在清洗解析结果...")

            try:
                chunks = clean_markdown(md_content, paper_id)
                _backup.save_stage_data(file_hash, "cleaning", _serialize_chunks(chunks))
                self._set_stage_status(
                    file_hash,
                    task_id,
                    file_path,
                    "cleaning",
                    "数据清洗完成",
                    "cleaning",
                    "completed",
                    paper_id=paper_id,
                )
            except Exception as e:
                stage_error = self._wrap_stage_error("cleaning", e)
                self._set_stage_status(
                    file_hash,
                    task_id,
                    file_path,
                    "error",
                    "数据清洗失败",
                    "cleaning",
                    "failed",
                    paper_id=paper_id,
                    error_msg=stage_error.detail["message"],
                )
                raise stage_error from e
        else:
            chunks = _backup.load_stage_data(file_hash, "cleaning") or []
            logger.info("跳过已完成阶段: cleaning")

        # ── Stage 4: 切块 ──
        chunked = None
        if _backup.get_backup(file_hash)["stages"].get("chunking") != "completed":
            self._set_stage_status(
                file_hash,
                task_id,
                file_path,
                "chunking",
                "切块中",
                "chunking",
                "running",
                paper_id=paper_id,
            )
            if progress_callback:
                await progress_callback("chunking", "正在切分文档...")

            try:
                chunked = chunk_text(chunks)
                _backup.save_stage_data(file_hash, "chunking", chunked)
                self._set_stage_status(
                    file_hash,
                    task_id,
                    file_path,
                    "chunking",
                    "切块完成",
                    "chunking",
                    "completed",
                    paper_id=paper_id,
                    extra={"chunk_count": len(chunked)},
                )
            except Exception as e:
                stage_error = self._wrap_stage_error("chunking", e)
                self._set_stage_status(
                    file_hash,
                    task_id,
                    file_path,
                    "error",
                    "切块失败",
                    "chunking",
                    "failed",
                    paper_id=paper_id,
                    error_msg=stage_error.detail["message"],
                )
                raise stage_error from e
        else:
            chunked = _backup.load_stage_data(file_hash, "chunking") or []
            logger.info("跳过已完成阶段: chunking")

        # ── Stage 5: Embedding ──
        vectors = None
        if _backup.get_backup(file_hash)["stages"].get("embedding") != "completed":
            self._set_stage_status(
                file_hash,
                task_id,
                file_path,
                "embedding",
                "向量化中",
                "embedding",
                "running",
                paper_id=paper_id,
            )
            if progress_callback:
                await progress_callback("embedding", "正在生成向量...")

            try:
                texts = [c["content"] for c in chunked]
                vectors = await self._embedding.embed(texts)
                _backup.save_stage_data(file_hash, "embedding", vectors)
                self._set_stage_status(
                    file_hash,
                    task_id,
                    file_path,
                    "embedding",
                    "向量化完成",
                    "embedding",
                    "completed",
                    paper_id=paper_id,
                )
            except Exception as e:
                stage_error = self._wrap_stage_error("embedding", e)
                self._set_stage_status(
                    file_hash,
                    task_id,
                    file_path,
                    "error",
                    "向量化失败",
                    "embedding",
                    "failed",
                    paper_id=paper_id,
                    error_msg=stage_error.detail["message"],
                )
                raise stage_error from e
        else:
            vectors = _backup.load_stage_data(file_hash, "embedding") or []
            logger.info("跳过已完成阶段: embedding")

        # ── Stage 6: 存储 ──
        self._set_stage_status(
            file_hash,
            task_id,
            file_path,
            "storing",
            "写入存储",
            "chroma",
            "running",
            paper_id=paper_id,
        )
        if progress_callback:
            await progress_callback("storing", "正在保存数据...")

        chroma = get_chroma()
        bm25 = get_bm25()

        try:
            stored_count = chroma.insert_chunks(
                paper_id=paper_id,
                chunks=[{**c, "file_hash": file_hash} for c in chunked],
                vectors=vectors,
            )

            texts = [c["content"] for c in chunked]
            doc_ids = [f"{paper_id}_{i}" for i in range(len(chunked))]
            bm25.add_documents(doc_ids, texts)

            # file_path 存储备份目录中的 PDF 路径（确保文件始终可访问）
            backup_pdf_path = _backup.get_pdf_path(file_hash) or file_path

            with sqlite.get_session() as session:
                session.execute(
                    text("""
                        INSERT INTO papers (paper_id, title, authors, file_path, file_hash,
                            file_size, chunk_count, import_time, status)
                        VALUES (:pid, :title, :authors, :path, :hash, :size, :chunks, :time, 'completed')
                    """),
                    {
                        "pid": paper_id,
                        "title": _guess_title(md_content, file_path),
                        "authors": "",
                        "path": backup_pdf_path,
                        "hash": file_hash,
                        "size": os.path.getsize(file_path),
                        "chunks": stored_count,
                        "time": import_time,
                    },
                )
                session.commit()
        except Exception as e:
            stage_error = self._wrap_stage_error("storing", e)
            self._set_stage_status(
                file_hash,
                task_id,
                file_path,
                "error",
                "写入存储失败",
                "chroma",
                "failed",
                paper_id=paper_id,
                error_msg=stage_error.detail["message"],
            )
            raise stage_error from e

        self._set_stage_status(
            file_hash,
            task_id,
            file_path,
            "completed",
            "导入完成",
            "chroma",
            "completed",
            paper_id=paper_id,
        )

        result = {
            "paper_id": paper_id,
            "task_id": task_id,
            "chunk_count": stored_count,
            "status": "completed",
        }
        if progress_callback:
            await progress_callback("completed", "导入完成", result)

        return result

    async def delete_paper(self, paper_id: str) -> None:
        """全量删除：Chroma + BM25 + SQLite + Backup"""
        chroma = get_chroma()
        bm25 = get_bm25()
        sqlite = get_sqlite()

        with sqlite.get_session() as session:
            result = session.execute(
                text("SELECT file_hash FROM papers WHERE paper_id = :pid"),
                {"pid": paper_id},
            )
            row = result.fetchone()
            if not row:
                raise AppError(2001, f"论文不存在: {paper_id}")

        file_hash = row[0]
        chroma.delete_paper(paper_id)
        bm25.delete_paper(paper_id)
        with sqlite.get_session() as session:
            session.execute(text("DELETE FROM papers WHERE paper_id = :pid"), {"pid": paper_id})
            session.execute(text("DELETE FROM import_logs WHERE paper_id = :pid"), {"pid": paper_id})
            session.commit()

        if file_hash:
            _backup.delete_backup(file_hash)

    async def close(self) -> None:
        await self._mineru.close()
        await self._vlm.close()
        await self._embedding.close()

    @staticmethod
    def _log(
        task_id: str,
        file_path: str,
        status: str,
        step: str,
        *,
        paper_id: str | None = None,
        error_msg: str | None = None,
    ) -> None:
        sqlite = get_sqlite()
        now = datetime.now(timezone.utc).isoformat()
        params = {
            "tid": task_id,
            "pid": paper_id,
            "path": file_path,
            "status": status,
            "step": step,
            "error": error_msg,
            "created": now,
            "updated": now,
        }
        with sqlite.get_session() as session:
            session.execute(
                text(
                    """
                    INSERT INTO import_logs (task_id, paper_id, file_path, status, current_step, error_msg, created_at, updated_at)
                    VALUES (:tid, :pid, :path, :status, :step, :error, :created, :updated)
                    ON CONFLICT(task_id) DO UPDATE SET
                        paper_id = COALESCE(excluded.paper_id, import_logs.paper_id),
                        file_path = excluded.file_path,
                        status = excluded.status,
                        current_step = excluded.current_step,
                        error_msg = excluded.error_msg,
                        updated_at = excluded.updated_at
                    """
                ),
                params,
            )
            session.commit()


def _hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


def _guess_title(md_content: str | None, file_path: str) -> str:
    if md_content:
        import re
        m = re.search(r"^#\s+(.+)$", md_content, re.MULTILINE)
        if m:
            return m.group(1).strip()
    return os.path.splitext(os.path.basename(file_path))[0]
