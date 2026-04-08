"""文献库路由.

支持 PDF 导入、列表查询、删除等操作。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile

from app.core.config import get_settings
from app.models.base import ApiResponse
from app.services.ingest_service import IngestWorkflow
from app.stores.qdrant_store import QdrantStore

settings = get_settings()
router = APIRouter(prefix="/library", tags=["library"])


def _get_workflow() -> IngestWorkflow:
    """获取导入工作流实例."""
    return IngestWorkflow()


def _get_store() -> QdrantStore:
    """获取 Qdrant 存储实例."""
    return QdrantStore()


@router.post("/import", response_model=ApiResponse)
async def import_pdf(file: UploadFile):
    """导入 PDF 文件.

    完整流程：MinerU 解析 → 清洗 → VLM 描述 → 切分 → Embedding → Qdrant 存储
    """
    # 保存上传文件
    upload_dir = Path(settings.sqlite_db_path).parent / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = upload_dir / file.filename

    with pdf_path.open("wb") as f:
        content = await file.read()
        f.write(content)

    # 执行导入
    try:
        workflow = _get_workflow()
        result = await workflow.ingest_pdf(pdf_path)
        return ApiResponse(data=result, message="导入成功")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


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
    """删除论文."""
    store = _get_store()
    store.delete_paper(paper_id)

    return ApiResponse(message="删除成功")


@router.get("/status", response_model=ApiResponse)
async def get_status():
    """获取系统状态."""
    workflow = _get_workflow()
    status = workflow.get_status()

    return ApiResponse(data=status)
