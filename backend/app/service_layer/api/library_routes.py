"""图书馆 API 路由"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from app.data_layer.storage.sqlite_runtime._types import ImportTask, LibraryItem, utc_now_iso
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
    return [LibraryItemOut(**item.__dict__) for item in items]


@router.get("/items/{item_id}", response_model=LibraryItemOut)
async def get_item(item_id: str, request: Request):
    container = request.app.state.container
    item = container.library_repo.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="文献不存在")
    return LibraryItemOut(**item.__dict__)


@router.delete("/items/{item_id}")
async def delete_item(item_id: str, request: Request):
    container = request.app.state.container
    item = container.library_repo.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="文献不存在")
    # 索引层软删除：RAG 检索排除该论文，但索引数据保留以便恢复
    try:
        container.document_ingest.delete_document(item_id)
    except Exception as e:
        logger.warning("索引软删除失败，继续 SQLite 软删除: %s", e)
    # SQLite 软删除：列表页排除该论文
    container.library_repo.soft_delete(item_id)
    logger.info("已软删除文献: %s (%s)", item.title, item_id)
    return {"status": "ok", "message": f"已移入回收站: {item.title}"}


@router.get("/trash", response_model=list[LibraryItemOut])
async def list_trashed(request: Request):
    container = request.app.state.container
    items = container.library_repo.list_trashed()
    return [LibraryItemOut(**item.__dict__) for item in items]


@router.post("/items/{item_id}/restore")
async def restore_item(item_id: str, request: Request):
    container = request.app.state.container
    item = container.library_repo.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="文献不存在")
    if item.deleted_at is None:
        raise HTTPException(status_code=400, detail="该文献不在回收站中")
    # 恢复索引层软删除标记
    try:
        container.document_ingest.restore_document(item_id)
    except Exception as e:
        logger.warning("索引层恢复失败: %s", e)
    # 恢复 SQLite 记录
    container.library_repo.restore(item_id)
    logger.info("已恢复文献: %s (%s)", item.title, item_id)
    return {"status": "ok", "message": f"已恢复: {item.title}"}


@router.delete("/items/{item_id}/permanent")
async def permanent_delete_item(item_id: str, request: Request):
    container = request.app.state.container
    item = container.library_repo.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="文献不存在")
    if item.deleted_at is None:
        raise HTTPException(status_code=400, detail="该文献不在回收站中，请先移入回收站")
    try:
        container.document_ingest.delete_document(item_id)
    except Exception as e:
        logger.warning("索引硬删除失败: %s", e)
    container.library_repo.hard_delete(item_id)
    logger.info("已永久删除文献: %s (%s)", item.title, item_id)
    return {"status": "ok", "message": f"已永久删除: {item.title}"}


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
    try:
        container.import_task_repo.update_status(task_id, "running")
        result = await container.document_ingest.ingest_document(file_path)
        if result.success:
            container.import_task_repo.update_status(
                task_id, "completed", message=f"导入成功，{result.chunk_count} 个 chunk", paper_id=result.paper_id,
            )
            # 从 PDF 文件读取实际页数和文件大小
            page_count = _read_pdf_page_count(file_path)
            file_size = _read_file_size(file_path)
            container.library_repo.upsert(LibraryItem(
                item_id=result.paper_id,
                title=file_path.stem,
                file_path=str(file_path),
                file_hash=_compute_file_hash(file_path),
                file_type=file_path.suffix.lower(),
                import_time=utc_now_iso(),
                page_count=page_count,
                status="ready",
                file_size=file_size,
            ))
        else:
            container.import_task_repo.update_status(task_id, "failed", message=result.error or "导入失败")
    except Exception as e:
        logger.error("后台导入失败 [%s]: %s", task_id, e, exc_info=True)
        container.import_task_repo.update_status(task_id, "failed", message=str(e))


@router.get("/import/{task_id}", response_model=ImportTaskOut)
async def get_import_status(task_id: str, request: Request):
    container = request.app.state.container
    task = container.import_task_repo.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return ImportTaskOut(**task.__dict__)


def _read_pdf_page_count(file_path: Path) -> int:
    """尝试从 PDF 文件读取实际页数，失败返回 0"""
    try:
        import pypdf
        with open(file_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            return len(reader.pages)
    except Exception:
        return 0


def _read_file_size(file_path: Path) -> int:
    """从文件系统读取文件大小"""
    try:
        return file_path.stat().st_size
    except Exception:
        return 0


def _compute_file_hash(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]
