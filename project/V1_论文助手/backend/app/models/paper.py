from __future__ import annotations

from pydantic import BaseModel


class PaperInfo(BaseModel):
    paper_id: str
    title: str
    authors: str
    file_path: str
    file_hash: str
    file_size: int | None = None
    chunk_count: int = 0
    total_pages: int | None = None
    import_time: str
    status: str = "completed"


class PaperListItem(BaseModel):
    paper_id: str
    title: str
    authors: str
    file_path: str
    file_hash: str
    chunk_count: int
    total_pages: int | None
    import_time: str
    status: str
