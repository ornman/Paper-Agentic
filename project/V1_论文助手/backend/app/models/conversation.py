from __future__ import annotations

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ConversationCreate(BaseModel):
    session_id: str


class ConversationResponse(BaseModel):
    session_id: str
    messages: list[ChatMessage]
