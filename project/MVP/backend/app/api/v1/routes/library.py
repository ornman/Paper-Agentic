# 文档库路由：/api/v1/library
# Task 3 只提供最小文档登记与状态管理接口，不引入 MinerU 或真正索引实现。

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.base import ApiResponse
from app.modules.library.models import DocumentImportRequest, DocumentReindexRequest
from app.modules.library.service import LibraryService

router = APIRouter(prefix="/library", tags=["library"])


def _get_service() -> LibraryService:
    """按需创建服务，避免模块导入时就触发数据库副作用。"""
    return LibraryService()


@router.post("/import", response_model=ApiResponse)
async def import_document(request: DocumentImportRequest):
    """登记一个待导入文档。"""
    record = _get_service().import_document(
        file_path=request.file_path,
        title=request.title,
        index_mode=request.index_mode,
        tags=request.tags,
    )
    return ApiResponse(data=record.model_dump())


@router.get("/documents", response_model=ApiResponse)
async def list_documents():
    """列出当前文档库记录。"""
    records = _get_service().list_documents()
    return ApiResponse(data=[record.model_dump() for record in records])


@router.delete("/documents/{document_id}", response_model=ApiResponse)
async def delete_document(document_id: str):
    """把文档状态推进到 deleted。"""
    try:
        record = _get_service().delete_document(document_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ApiResponse(data=record.model_dump(), message="删除成功")


@router.post("/documents/{document_id}/reindex", response_model=ApiResponse)
async def reindex_document(document_id: str, request: DocumentReindexRequest | None = None):
    """重建索引占位接口。"""
    try:
        record = _get_service().reindex_document(
            document_id=document_id,
            index_mode=request.index_mode if request else None,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ApiResponse(data=record.model_dump())
