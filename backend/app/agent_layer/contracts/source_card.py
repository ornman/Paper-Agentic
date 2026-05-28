from __future__ import annotations

from pydantic import BaseModel


class SourceCard(BaseModel):
    id: str
    paper_id: str | None = None
    title: str
    page: int | None = None
    section: str | None = None
    file_path: str | None = None
    local_path: str | None = None
    content: str | None = None
    import_time: str | None = None
