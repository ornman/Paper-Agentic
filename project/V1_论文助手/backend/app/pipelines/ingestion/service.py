"""导入管道服务：编排 MinerU → VLM图片描述 → 清洗 → 切块 → Embedding → 存储"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.api.v1.deps import get_bm25, get_redis, get_sqlite, get_zvec
from app.clients.embedding_client import EmbeddingClient
from app.clients.mineru_client import MinerUClient
from app.clients.vlm_client import VLMClient
from app.pipelines.ingestion.chunker import chunk_text
from app.pipelines.ingestion.cleaner import clean_markdown
from app.pipelines.ingestion.image_handler import inject_image_descriptions

logger = logging.getLogger("paper-assistant")


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

        paper_id = uuid.uuid4().hex[:16]
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

        # ── Stage 1: MinerU 解析 ──
        self._log(sqlite, task_id, file_path, "parsing", "MinerU 解析中")
        if progress_callback:
            await progress_callback("parsing", "正在提交 PDF 解析...")

        mineru_result = await self._mineru.run(file_path)
        md_content = mineru_result.md_content or ""
        paper_dir = mineru_result.paper_dir
        images_dir = os.path.join(paper_dir, "images")

        # ── Stage 2: VLM 图片描述注入（对原始 MD 操作） ──
        self._log(sqlite, task_id, file_path, "vlm", "图片理解中")
        if progress_callback:
            await progress_callback("vlm", "正在处理图片...")

        if md_content and os.path.isdir(images_dir):
            md_content = await inject_image_descriptions(
                md_content, images_dir, paper_dir, self._vlm, concurrency=10,
            )
            # 写回带描述的 MD
            desc_path = os.path.join(paper_dir, "full_with_desc.md")
            with open(desc_path, "w", encoding="utf-8") as f:
                f.write(md_content)

        # ── Stage 3: 清洗（在带描述的 MD 上操作） ──
        self._log(sqlite, task_id, file_path, "cleaning", "数据清洗中")
        if progress_callback:
            await progress_callback("cleaning", "正在清洗解析结果...")

        chunks = clean_markdown(md_content, paper_id)

        # ── Stage 4: 切块 ──
        self._log(sqlite, task_id, file_path, "chunking", "切块中")
        if progress_callback:
            await progress_callback("chunking", "正在切分文档...")

        chunked = chunk_text(chunks)

        # ── Stage 5: Embedding ──
        self._log(sqlite, task_id, file_path, "embedding", "向量化中")
        if progress_callback:
            await progress_callback("embedding", "正在生成向量...")

        texts = [c["content"] for c in chunked]
        vectors = await self._embedding.embed(texts)

        # ── Stage 6: 存储 ──
        self._log(sqlite, task_id, file_path, "storing", "写入存储")
        if progress_callback:
            await progress_callback("storing", "正在保存数据...")

        zvec = get_zvec()
        bm25 = get_bm25()

        stored_count = zvec.insert_chunks(
            paper_id=paper_id,
            chunks=[{**c, "file_hash": file_hash} for c in chunked],
            vectors=vectors,
        )

        doc_ids = [f"{paper_id}_{i}" for i in range(len(chunked))]
        bm25.add_documents(doc_ids, texts)

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
                    "path": file_path,
                    "hash": file_hash,
                    "size": os.path.getsize(file_path),
                    "chunks": stored_count,
                    "time": import_time,
                },
            )
            session.commit()

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
        """全量删除：Zvec + BM25 + SQLite"""
        zvec = get_zvec()
        bm25 = get_bm25()
        sqlite = get_sqlite()

        zvec.delete_paper(paper_id)
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
