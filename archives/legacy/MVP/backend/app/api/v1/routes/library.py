"""文献库路由（新架构）.

支持 PDF 导入、列表查询、删除等操作。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, UploadFile

from app.core.config import get_settings
from app.core.error_messages import format_user_error, get_http_status_code
from app.core.errors import IngestionError
from app.models.base import ApiResponse
from app.modules.library.service import LibraryService
from app.stores.qdrant_store import QdrantStore

settings = get_settings()
router = APIRouter(prefix="/library", tags=["library"])


def _get_library_service() -> LibraryService:
    """获取图书馆服务实例."""
    return LibraryService()


def _get_store() -> QdrantStore:
    """获取 Qdrant 存储实例."""
    return QdrantStore()


@router.post("/import", response_model=ApiResponse)
async def import_pdf(file: UploadFile):
    """导入 PDF 文件（上传方式）.

    完整流程：MinerU 解析 → 清洗 → VLM 描述 → 切分 → Embedding → Qdrant 存储
    """
    # 保存上传文件
    upload_dir = Path(settings.sqlite_db_path).parent / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = upload_dir / file.filename

    with pdf_path.open("wb") as f:
        content = await file.read()
        f.write(content)

    # 执行导入（使用新架构）
    try:
        service = _get_library_service()
        result = await service.import_pdf(file_path=str(pdf_path))
        return ApiResponse(
            data={
                "document_id": result.document_id,
                "title": result.title,
                "status": result.status,
            },
            message="导入成功",
        )
    except IngestionError as e:
        # 处理业务错误，提供用户友好的错误信息
        error_info = format_user_error(e.code, {"detail": e.detail})
        status_code = get_http_status_code(error_info["severity"])
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": error_info["code"],
                "message": error_info["user_message"],
                "suggestion": error_info["suggestion"],
                "severity": error_info["severity"],
            },
        ) from e
    except Exception as e:
        # 处理未预期的错误
        error_info = format_user_error("internal_error", {"detail": str(e)})
        raise HTTPException(
            status_code=500,
            detail={
                "code": error_info["code"],
                "message": error_info["user_message"],
                "suggestion": error_info["suggestion"],
                "severity": error_info["severity"],
            },
        ) from e


@router.post("/import-path", response_model=ApiResponse)
async def import_pdf_by_path(
    file_path: str = Body(..., description="PDF 文件的完整路径"),
    title: str = Body("", description="可选标题（默认使用文件名）"),
    index_mode: str = Body("distributed", description="索引模式（distributed/brute）"),
):
    """导入 PDF 文件（文件路径方式）.

    适用于本地已有 PDF 文件的场景。

    Args:
        file_path: PDF 文件的完整路径
        title: 可选标题（默认使用文件名）
        index_mode: 索引模式（distributed/brute）
    """
    # 执行导入
    try:
        service = _get_library_service()
        result = await service.import_pdf(
            file_path=file_path,
            title=title,
            index_mode=index_mode,
        )
        return ApiResponse(
            data={
                "document_id": result.document_id,
                "title": result.title,
                "status": result.status,
            },
            message="导入成功",
        )
    except IngestionError as e:
        # 处理业务错误，提供用户友好的错误信息
        error_info = format_user_error(e.code, {"detail": e.detail})
        status_code = get_http_status_code(error_info["severity"])
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": error_info["code"],
                "message": error_info["user_message"],
                "suggestion": error_info["suggestion"],
                "severity": error_info["severity"],
            },
        ) from e
    except Exception as e:
        # 处理未预期的错误
        error_info = format_user_error("internal_error", {"detail": str(e)})
        raise HTTPException(
            status_code=500,
            detail={
                "code": error_info["code"],
                "message": error_info["user_message"],
                "suggestion": error_info["suggestion"],
                "severity": error_info["severity"],
            },
        ) from e


@router.post("/resume/{document_id}", response_model=ApiResponse)
async def resume_import(document_id: str):
    """恢复失败的导入任务（断点续传）.

    支持从失败阶段自动恢复并继续执行。
    """
    try:
        service = _get_library_service()
        result = await service.resume_import(document_id)
        return ApiResponse(
            data={
                "document_id": result.document_id,
                "title": result.title,
                "status": result.status,
            },
            message="恢复导入成功",
        )
    except KeyError as e:
        error_info = format_user_error("file_not_found", {"document_id": document_id})
        raise HTTPException(
            status_code=404,
            detail={
                "code": error_info["code"],
                "message": error_info["user_message"],
                "suggestion": error_info["suggestion"],
                "severity": error_info["severity"],
            },
        ) from e
    except ValueError as e:
        error_info = format_user_error("invalid_file_format", {"detail": str(e)})
        status_code = get_http_status_code(error_info["severity"])
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": error_info["code"],
                "message": error_info["user_message"],
                "suggestion": error_info["suggestion"],
                "severity": error_info["severity"],
            },
        ) from e
    except Exception as e:
        error_info = format_user_error("internal_error", {"detail": str(e)})
        raise HTTPException(
            status_code=500,
            detail={
                "code": error_info["code"],
                "message": error_info["user_message"],
                "suggestion": error_info["suggestion"],
                "severity": error_info["severity"],
            },
        ) from e


@router.get("/papers", response_model=ApiResponse)
async def list_papers():
    """列出所有已入库的论文."""
    store = _get_store()
    papers = store.list_papers()

    # 获取每篇论文的详细信息
    paper_info = []
    for paper_id in papers:
        info = store.get_paper_info(paper_id)
        if info:
            paper_info.append({
                "paper_id": paper_id,
                "chunks_count": info["points_count"],
                "vector_size": info["vector_size"],
            })

    return ApiResponse(data=paper_info)


@router.get("/papers/{paper_id}", response_model=ApiResponse)
async def get_paper(paper_id: str):
    """获取论文详情."""
    store = _get_store()
    info = store.get_paper_info(paper_id)

    if info is None:
        raise HTTPException(status_code=404, detail=f"论文不存在: {paper_id}")

    return ApiResponse(data={
        "paper_id": paper_id,
        "chunks_count": info["points_count"],
        "vector_size": info["vector_size"],
    })


@router.delete("/papers/{paper_id}", response_model=ApiResponse)
async def delete_paper(paper_id: str):
    """删除论文（包括 Qdrant collection 和文件系统数据）.

    删除内容：
    1. Qdrant 向量库中的 collection
    2. 文件系统中的论文数据目录（MinerU 解析结果、图片、缓存等）
    """
    store = _get_store()

    # 1. 删除 Qdrant collection
    store.delete_paper(paper_id)

    # 2. 删除文件系统中的论文数据
    papers_dir = Path(settings.sqlite_db_path).parent / "papers" / paper_id

    if papers_dir.exists():
        shutil.rmtree(papers_dir)

    return ApiResponse(message=f"论文 {paper_id} 已删除")


@router.get("/status", response_model=ApiResponse)
async def get_status():
    """获取系统状态."""
    store = _get_store()
    papers = store.list_papers()

    return ApiResponse(data={
        "papers_count": len(papers),
        "total_chunks": store.count,
        "papers": papers,
    })
