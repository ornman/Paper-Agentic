"""图书馆 Schema"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LibraryItemOut(BaseModel):
    item_id: str
    title: str
    file_path: str
    file_hash: str = ""
    file_type: str = ""
    import_time: str = ""
    page_count: int = 0
    status: str = "ready"
    authors: str = ""
    year: int | None = None
    chunk_count: int = 0


class ImportTaskOut(BaseModel):
    task_id: str
    file_path: str
    status: str = "queued"
    message: str = ""
    created_at: str = ""
    paper_id: str = ""
    completed_at: str = ""


class ImportRequest(BaseModel):
    file_path: str = Field(..., description="PDF/DOCX 文件路径")


class ImportResponse(BaseModel):
    task_id: str
    status: str
    message: str = ""


# ── 前端兼容 Schema ──


class PaperItemOut(BaseModel):
    """前端兼容的论文项"""
    paper_id: str
    title: str
    authors: str = ""
    year: int | None = None
    file_path: str
    file_hash: str = ""
    chunk_count: int = 0
    total_pages: int = 0
    import_time: str = ""
    status: str = "ready"


class PaperListResponse(BaseModel):
    papers: list[PaperItemOut]


class ImportStartResponse(BaseModel):
    task_id: str
    status: str


class ImportStatusResponse(BaseModel):
    task_id: str
    paper_id: str | None = None
    status: str
    current_step: str | None = None
    error_msg: str | None = None
    file_name: str | None = None
    percent: float | None = None
