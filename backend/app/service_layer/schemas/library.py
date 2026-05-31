"""图书馆 Schema"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class LibraryItemOut(BaseModel):
    """文献项输出（兼容前端 PaperItem 接口）"""
    item_id: str
    library_item_id: str = ""   # 前端兼容别名（= item_id）
    paper_id: str = ""          # 前端兼容别名（= item_id）
    title: str
    authors: str = ""
    year: int | None = None
    file_path: str
    file_hash: str = ""
    file_type: str = ""
    kind: str = ""              # 前端兼容别名（= file_type）
    import_time: str = ""
    page_count: int = 0
    total_pages: int = 0        # 前端兼容别名（= page_count）
    chunk_count: int = 0
    status: str = "ready"
    keywords: list[str] = []
    file_size: int | None = None

    @model_validator(mode="after")
    def _set_aliases(self) -> "LibraryItemOut":
        if not self.library_item_id:
            self.library_item_id = self.item_id
        if not self.paper_id:
            self.paper_id = self.item_id
        if not self.kind:
            self.kind = self.file_type
        if not self.total_pages:
            self.total_pages = self.page_count
        return self


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
