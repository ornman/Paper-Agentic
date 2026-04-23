"""论文管理 API"""

from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import FileResponse
from sqlalchemy import text

from app.api.v1.deps import get_chroma, get_sqlite, get_bm25
from app.core.errors import AppError
from app.models.paper import PaperListItem
from app.pipelines.ingestion.backup_manager import BackupManager

router = APIRouter(prefix="/papers", tags=["papers"])

_backup = BackupManager()


@router.get("")
async def list_papers():
    sqlite = get_sqlite()
    with sqlite.get_session() as session:
        result = session.execute(text(
            "SELECT paper_id, title, authors, chunk_count, total_pages, import_time, status "
            "FROM papers ORDER BY import_time DESC"
        ))
        papers = [
            PaperListItem(
                paper_id=row[0],
                title=row[1],
                authors=row[2],
                chunk_count=row[3],
                total_pages=row[4],
                import_time=row[5],
                status=row[6],
            )
            for row in result.fetchall()
        ]
    return {"papers": [p.model_dump() for p in papers]}


@router.get("/{paper_id}/open")
async def open_paper(paper_id: str):
    """获取论文 PDF 文件（从备份目录）"""
    sqlite = get_sqlite()
    with sqlite.get_session() as session:
        result = session.execute(
            text("SELECT file_hash, title, file_path FROM papers WHERE paper_id = :pid"),
            {"pid": paper_id},
        )
        row = result.fetchone()
        if not row:
            raise AppError(2001, f"论文不存在: {paper_id}")

    file_hash, title, file_path = row[0], row[1], row[2]

    # 优先从备份目录获取 PDF
    pdf_path = _backup.get_pdf_path(file_hash)
    if pdf_path and os.path.exists(pdf_path):
        filename = f"{title or paper_id}.pdf"
        return FileResponse(pdf_path, filename=filename, media_type="application/pdf")

    # 降级：使用原始路径
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=f"{title or paper_id}.pdf", media_type="application/pdf")

    raise AppError(2002, f"PDF 文件不存在: {paper_id}")


@router.delete("/{paper_id}")
async def delete_paper(paper_id: str):
    sqlite = get_sqlite()
    with sqlite.get_session() as session:
        result = session.execute(
            text("SELECT paper_id FROM papers WHERE paper_id = :pid"),
            {"pid": paper_id},
        )
        if not result.fetchone():
            raise AppError(2001, f"论文不存在: {paper_id}")

        session.execute(text("DELETE FROM papers WHERE paper_id = :pid"), {"pid": paper_id})
        session.commit()

    chroma = get_chroma()
    chroma.delete_paper(paper_id)

    bm25 = get_bm25()
    bm25.delete_paper(paper_id)

    return {"status": "deleted", "paper_id": paper_id}
