from __future__ import annotations

from pydantic import BaseModel


class QueryRequest(BaseModel):
    session_id: str
    prompt: str = ""
    selection: str = ""
    draft: str = ""
    paper_ids: list[str] | None = None
    enable_rag: bool = True  # 是否启用 RAG 检索，默认启用


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
