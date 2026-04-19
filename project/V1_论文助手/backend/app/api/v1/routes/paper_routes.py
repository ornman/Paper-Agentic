"""论文管理 API"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.v1.deps import get_sqlite, get_zvec, get_bm25
from app.core.errors import AppError
from app.models.paper import PaperListItem

router = APIRouter(prefix="/papers", tags=["papers"])


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

    zvec = get_zvec()
    zvec.delete_paper(paper_id)

    bm25 = get_bm25()
    bm25.delete_paper(paper_id)

    return {"status": "deleted", "paper_id": paper_id}
