"""图书馆 API 路由"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from app.data_layer.contracts.library_item import ImportTask, LibraryItem
from app.data_layer.preprocessing.transformation.pdf_metadata import extract_pdf_metadata
from app.service_layer.schemas.library import (
    ImportRequest,
    ImportResponse,
    ImportTaskOut,
    LibraryItemOut,
)

logger = logging.getLogger("paper-assistant")

router = APIRouter(prefix="/library", tags=["library"])


@router.get("/items", response_model=list[LibraryItemOut])
async def list_items(request: Request):
    container = request.app.state.container
    items = container.library_repo.list_items()
    return [_item_to_out(item) for item in items]


@router.get("/items/{item_id}", response_model=LibraryItemOut)
async def get_item(item_id: str, request: Request):
    container = request.app.state.container
    item = container.library_repo.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="文献不存在")
    return _item_to_out(item)


@router.delete("/items/{item_id}")
async def delete_item(item_id: str, request: Request):
    container = request.app.state.container
    item = container.library_repo.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="文献不存在")
    container.document_ingest.delete_document(item_id)
    container.library_repo.delete(item_id)
    return {"status": "ok", "message": f"已删除: {item.title}"}


@router.post("/items/{item_id}/retry")
async def retry_import(item_id: str, request: Request):
    container = request.app.state.container
    item = container.library_repo.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="文献不存在")

    file_path = Path(item.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=400, detail=f"原始文件不存在: {item.file_path}")

    # Remove failed record so re-import is clean
    container.library_repo.delete(item_id)

    task_id = uuid.uuid4().hex[:12]
    task = ImportTask(task_id=task_id, file_path=str(file_path))
    container.import_task_repo.create(task)
    asyncio.create_task(_run_import(container, task_id, file_path))

    return {"task_id": task_id, "status": "queued"}


@router.post("/import", response_model=ImportResponse)
async def import_document(body: ImportRequest, request: Request):
    container = request.app.state.container
    file_path = Path(body.file_path)

    if not file_path.exists():
        raise HTTPException(status_code=400, detail=f"文件不存在: {body.file_path}")
    if file_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="仅支持 PDF 格式")

    file_hash = _compute_file_hash(file_path)
    existing = container.library_repo.get_by_hash(file_hash)
    if existing:
        return ImportResponse(
            task_id="",
            status="duplicate",
            message=f"文件已导入: {existing.title}",
        )

    task_id = uuid.uuid4().hex[:12]
    task = ImportTask(task_id=task_id, file_path=str(file_path))
    container.import_task_repo.create(task)

    # 后台执行导入
    asyncio.create_task(_run_import(container, task_id, file_path))

    return ImportResponse(task_id=task_id, status="queued", message="导入任务已创建")


async def _run_import(container, task_id: str, file_path: Path):
    """后台导入 worker"""
    meta = extract_pdf_metadata(file_path)
    fallback_item_id = file_path.stem

    try:
        container.import_task_repo.update_status(task_id, "running")
        result = await container.document_ingest.ingest_document(file_path)
        if result.success:
            container.import_task_repo.update_status(
                task_id, "completed", message=f"导入成功，{result.chunk_count} 个 chunk", paper_id=result.paper_id,
            )
            container.library_repo.upsert(LibraryItem(
                item_id=result.paper_id,
                title=meta.title or file_path.stem,
                file_path=str(file_path),
                file_type=file_path.suffix.lower(),
                status="ready",
                authors=meta.authors,
                year=meta.year,
            ))
        else:
            container.import_task_repo.update_status(task_id, "failed", message=result.error or "导入失败")
            container.library_repo.upsert(LibraryItem(
                item_id=fallback_item_id,
                title=meta.title or file_path.stem,
                file_path=str(file_path),
                file_type=file_path.suffix.lower(),
                status="failed",
                authors=meta.authors,
                year=meta.year,
            ))
    except Exception as e:
        logger.error("后台导入失败 [%s]: %s", task_id, e, exc_info=True)
        container.import_task_repo.update_status(task_id, "failed", message=str(e))
        container.library_repo.upsert(LibraryItem(
            item_id=fallback_item_id,
            title=meta.title or file_path.stem,
            file_path=str(file_path),
            file_type=file_path.suffix.lower(),
            status="failed",
            authors=meta.authors,
            year=meta.year,
        ))


@router.get("/import/{task_id}", response_model=ImportTaskOut)
async def get_import_status(task_id: str, request: Request):
    container = request.app.state.container
    task = container.import_task_repo.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return ImportTaskOut(**task.__dict__)


def _compute_file_hash(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _item_to_out(item: LibraryItem) -> LibraryItemOut:
    return LibraryItemOut(
        library_item_id=item.item_id,
        kind=item.file_type.lstrip(".") or "pdf",
        title=item.title,
        file_path=item.file_path,
        file_hash=item.file_hash,
        authors=item.authors,
        year=item.year,
        total_pages=item.page_count or None,
        status=item.status,
        import_time=item.import_time,
    )
