"""论文管理 API — 前端兼容路由"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from app.service_layer.schemas.library import PaperItemOut, PaperListResponse

router = APIRouter(tags=["papers"])


@router.get("/papers", response_model=PaperListResponse)
async def list_papers(
    request: Request,
    title: str | None = Query(None, description="标题模糊搜索"),
    authors: str | None = Query(None, description="作者精确筛选"),
    year_from: int | None = Query(None, description="年份起始"),
    year_to: int | None = Query(None, description="年份截止"),
):
    container = request.app.state.container
    has_filter = any(v is not None for v in (title, authors, year_from, year_to))
    if has_filter:
        items = container.library_repo.list_items_filtered(
            title=title, authors=authors, year_from=year_from, year_to=year_to,
        )
    else:
        items = container.library_repo.list_items()
    papers = [
        PaperItemOut(
            paper_id=item.item_id,
            title=item.title,
            authors=item.authors,
            year=item.year,
            file_path=item.file_path,
            file_hash=item.file_hash,
            chunk_count=getattr(item, "chunk_count", 0),
            total_pages=item.page_count or 0,
            import_time=item.import_time,
            status=item.status,
        )
        for item in items
    ]
    return PaperListResponse(papers=papers)


@router.get("/papers/{paper_id}/open")
async def open_paper(paper_id: str, request: Request):
    container = request.app.state.container
    item = container.library_repo.get(paper_id)
    if not item:
        raise HTTPException(status_code=404, detail="论文不存在")

    paper_dir = container.directory_manager._papers_dir / paper_id
    if not paper_dir.exists():
        raise HTTPException(status_code=404, detail="论文文件不存在")

    for f in paper_dir.iterdir():
        if f.is_file() and f.suffix.lower() == ".pdf":
            media_type = (
                "application/pdf"
                if f.suffix.lower() == ".pdf"
                else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            return FileResponse(path=str(f), media_type=media_type, filename=f.name)

    raise HTTPException(status_code=404, detail="论文文件不存在")


@router.delete("/papers/{paper_id}")
async def delete_paper(paper_id: str, request: Request):
    container = request.app.state.container
    item = container.library_repo.get(paper_id)
    if not item:
        raise HTTPException(status_code=404, detail="论文不存在")
    container.document_ingest.delete_document(paper_id)
    return {"status": "ok", "message": f"已删除: {item.title}"}
