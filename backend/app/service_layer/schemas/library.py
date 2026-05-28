"""图书馆 Schema"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LibraryItemOut(BaseModel):
    library_item_id: str
    kind: str
    title: str
    file_path: str
    file_hash: str
    authors: str = ""
    file_size: int | None = None
    chunk_count: int = 0
    total_pages: int | None = None
    status: str = "completed"
    import_time: str = ""


class ImportTaskOut(BaseModel):
    task_id: str
    file_path: str
    status: str = "queued"
    current_stage: str = "queued"
    library_item_id: str | None = None
    error_message: str | None = None
    created_at: str = ""
    updated_at: str = ""


class ImportRequest(BaseModel):
    file_path: str = Field(..., description="PDF/DOCX 文件路径")


class ImportResponse(BaseModel):
    task_id: str
    status: str
    message: str = ""
