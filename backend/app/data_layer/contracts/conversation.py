from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConversationSession:
    session_id: str
    title: str
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ConversationMessage:
    session_id: str
    role: str
    content: str
    created_at: str = ""
    sources_json: str | None = None
