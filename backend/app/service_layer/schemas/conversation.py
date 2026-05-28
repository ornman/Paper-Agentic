"""对话 Schema"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(default="", description="会话 ID，为空则自动创建")
    message: str = Field(..., description="用户消息")
    paper_ids: list[str] | None = Field(default=None, description="限定检索的论文 ID 列表")


class ChatResponse(BaseModel):
    session_id: str
    event: str
    data: dict


class ConversationSessionOut(BaseModel):
    session_id: str
    title: str
    created_at: str = ""
    updated_at: str = ""


class ConversationMessageOut(BaseModel):
    session_id: str
    role: str
    content: str
    created_at: str = ""
    sources_json: str | None = None
