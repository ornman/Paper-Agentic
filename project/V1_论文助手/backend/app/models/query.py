from __future__ import annotations

from pydantic import BaseModel


class QueryRequest(BaseModel):
    session_id: str
    prompt: str = ""
    selection: str = ""
    draft: str = ""
    paper_ids: list[str] | None = None


class SourceRef(BaseModel):
    paper_id: str
    title: str
    page: int
    section: str
    local_path: str


class QueryMetadata(BaseModel):
    session_id: str
    source_count: int
    sources: list[SourceRef]
