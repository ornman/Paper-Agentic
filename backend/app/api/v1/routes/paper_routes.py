"""论文管理 API"""

from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import FileResponse
from sqlalchemy import text

from app.api.v1.deps import get_bm25, get_chroma, get_sqlite
from app.core.errors import AppError
from app.models.paper import PaperListItem
from app.pipelines.ingestion.backup_manager import BackupManager
from app.pipelines.ingestion.service import IngestionService

router = APIRouter(prefix="/papers", tags=["papers"])

_backup = BackupManager()


@router.get("")
async def list_papers():
    sqlite = get_sqlite()
    with sqlite.get_session() as session:
        result = session.execute(text(
            "SELECT paper_id, title, authors, file_path, file_hash, chunk_count, total_pages, import_time, status "
            "FROM papers ORDER BY import_time DESC"
        ))
        papers = [
            PaperListItem(
                paper_id=row[0],
                title=row[1],
                authors=row[2],
                file_path=row[3],
                file_hash=row[4],
                chunk_count=row[5],
                total_pages=row[6],
                import_time=row[7],
                status=row[8],
            )
            for row in result.fetchall()
        ]
    return {"papers": [paper.model_dump() for paper in papers]}


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

    pdf_path = _backup.get_pdf_path(file_hash)
    if pdf_path and os.path.exists(pdf_path):
        filename = f"{title or paper_id}.pdf"
        return FileResponse(pdf_path, filename=filename, media_type="application/pdf")

    if os.path.exists(file_path):
        return FileResponse(file_path, filename=f"{title or paper_id}.pdf", media_type="application/pdf")

    raise AppError(2002, f"PDF 文件不存在: {paper_id}")


@router.delete("/{paper_id}")
async def delete_paper(paper_id: str):
    service = IngestionService()
    await service.delete_paper(paper_id)
    return {"status": "deleted", "paper_id": paper_id}
