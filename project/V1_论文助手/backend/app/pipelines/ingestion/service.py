"""导入管道服务：编排 MinerU → VLM图片描述 → 清洗 → 切块 → Embedding → 存储"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.api.v1.deps import get_bm25, get_chroma, get_sqlite
from app.clients.embedding_client import EmbeddingClient
from app.clients.mineru_client import MinerUClient
from app.clients.vlm_client import VLMClient
from app.pipelines.ingestion.backup_manager import BackupManager
from app.pipelines.ingestion.chunker import chunk_text
from app.pipelines.ingestion.cleaner import clean_markdown
from app.pipelines.ingestion.image_handler import inject_image_descriptions

logger = logging.getLogger("paper-assistant")

_backup = BackupManager()


class IngestionService:
    def __init__(self):
        self._mineru = MinerUClient()
        self._vlm = VLMClient()
        self._embedding = EmbeddingClient()

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
        sqlite = get_sqlite()

        # 去重
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
            _backup.create(file_hash, file_path, paper_id)

        # ── Stage 1: MinerU 解析 ──
        md_content = ""
        paper_dir = ""
        images_dir = ""

        if _backup.get_backup(file_hash)["stages"].get("mineru") != "completed":
            self._log(sqlite, task_id, file_path, "parsing", "MinerU 解析中")
            if progress_callback:
                await progress_callback("parsing", "正在提交 PDF 解析...")

            try:
                mineru_result = await self._mineru.run(file_path)
                md_content = mineru_result.md_content or ""
                paper_dir = mineru_result.paper_dir
                images_dir = os.path.join(paper_dir, "images")

                _backup.save_stage_data(file_hash, "mineru", md_content)
                _backup.update_stage(file_hash, "mineru", "completed")
            except Exception as e:
                _backup.update_stage(file_hash, "mineru", "failed")
                raise
        else:
            md_content = _backup.load_stage_data(file_hash, "mineru") or ""
            logger.info("跳过已完成阶段: mineru")

        # ── Stage 2: VLM 图片描述注入（可降级） ──
        vlm_stage = _backup.get_backup(file_hash)["stages"].get("vlm")
        if vlm_stage not in ("completed", "skipped"):
            self._log(sqlite, task_id, file_path, "vlm", "图片理解中")
            if progress_callback:
                await progress_callback("vlm", "正在处理图片...")

            try:
                if not paper_dir:
                    paper_dir = os.path.join("./data/papers", task_id)
                    images_dir = os.path.join(paper_dir, "images")

                if md_content and os.path.isdir(images_dir):
                    md_content = await inject_image_descriptions(
                        md_content, images_dir, paper_dir, self._vlm,
                        concurrency=10, on_error="default",
                    )

                _backup.save_stage_data(file_hash, "vlm", md_content)
                _backup.update_stage(file_hash, "vlm", "completed")
            except Exception as e:
                logger.warning("VLM 阶段整体失败，降级跳过: %s", e)
                _backup.update_stage(file_hash, "vlm", "skipped")
        else:
            md_content = _backup.load_stage_data(file_hash, "vlm") or ""
            logger.info("跳过已完成阶段: vlm")

        # ── Stage 3: 清洗 ──
        chunks = clean_markdown(md_content, paper_id)
        self._log(sqlite, task_id, file_path, "cleaning", "数据清洗中")
        if progress_callback:
            await progress_callback("cleaning", "正在清洗解析结果...")

        # ── Stage 4: 切块 ──
        chunked = None
        if _backup.get_backup(file_hash)["stages"].get("chunking") != "completed":
            self._log(sqlite, task_id, file_path, "chunking", "切块中")
            if progress_callback:
                await progress_callback("chunking", "正在切分文档...")

            try:
                chunked = chunk_text(chunks)
                _backup.save_stage_data(file_hash, "chunking", chunked)
                _backup.update_stage(file_hash, "chunking", "completed",
                                     extra={"chunk_count": len(chunked)})
            except Exception as e:
                _backup.update_stage(file_hash, "chunking", "failed")
                raise
        else:
            chunked = _backup.load_stage_data(file_hash, "chunking") or []
            logger.info("跳过已完成阶段: chunking")

        # ── Stage 5: Embedding ──
        vectors = None
        if _backup.get_backup(file_hash)["stages"].get("embedding") != "completed":
            self._log(sqlite, task_id, file_path, "embedding", "向量化中")
            if progress_callback:
                await progress_callback("embedding", "正在生成向量...")

            try:
                texts = [c["content"] for c in chunked]
                vectors = await self._embedding.embed(texts)
                _backup.save_stage_data(file_hash, "embedding", vectors)
                _backup.update_stage(file_hash, "embedding", "completed")
            except Exception as e:
                _backup.update_stage(file_hash, "embedding", "failed")
                raise
        else:
            vectors = _backup.load_stage_data(file_hash, "embedding") or []
            logger.info("跳过已完成阶段: embedding")

        # ── Stage 6: 存储 ──
        self._log(sqlite, task_id, file_path, "storing", "写入存储")
        if progress_callback:
            await progress_callback("storing", "正在保存数据...")

        chroma = get_chroma()
        bm25 = get_bm25()

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

        _backup.update_stage(file_hash, "chroma", "completed")
        self._log(sqlite, task_id, file_path, "completed", "", paper_id=paper_id)

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
        """全量删除：Chroma + BM25 + SQLite"""
        chroma = get_chroma()
        bm25 = get_bm25()
        sqlite = get_sqlite()

        chroma.delete_paper(paper_id)
        bm25.delete_paper(paper_id)
        with sqlite.get_session() as session:
            session.execute(text("DELETE FROM papers WHERE paper_id = :pid"), {"pid": paper_id})
            session.execute(text("DELETE FROM import_logs WHERE paper_id = :pid"), {"pid": paper_id})
            session.commit()

    async def close(self) -> None:
        await self._mineru.close()
        await self._vlm.close()
        await self._embedding.close()

    @staticmethod
    def _log(sqlite, task_id: str, file_path: str, status: str, step: str,
             paper_id: str | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite.get_session() as session:
            existing = session.execute(
                text("SELECT id FROM import_logs WHERE task_id = :tid"),
                {"tid": task_id},
            ).fetchone()

            if existing:
                params = {"status": status, "step": step, "updated": now, "tid": task_id}
                if paper_id:
                    session.execute(
                        text("UPDATE import_logs SET status=:status, current_step=:step, "
                             "updated_at=:updated, paper_id=:pid WHERE task_id=:tid"),
                        {**params, "pid": paper_id},
                    )
                else:
                    session.execute(
                        text("UPDATE import_logs SET status=:status, current_step=:step, "
                             "updated_at=:updated WHERE task_id=:tid"),
                        params,
                    )
            else:
                session.execute(
                    text("""
                        INSERT INTO import_logs (task_id, file_path, status, current_step,
                            created_at, updated_at)
                        VALUES (:tid, :path, :status, :step, :created, :updated)
                    """),
                    {
                        "tid": task_id, "path": file_path, "status": status,
                        "step": step, "created": now, "updated": now,
                    },
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
