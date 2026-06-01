"""图书馆 API 路由"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.data_layer.storage.sqlite_runtime._types import LibraryItem, utc_now_iso
from app.service_layer.schemas.library import LibraryItemOut

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
