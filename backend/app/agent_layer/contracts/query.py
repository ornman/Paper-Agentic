from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from .used_inputs import UsedInputs


class AskRequest(BaseModel):
    session_id: str
    prompt: str
    selection: str | None = None
    draft: str | None = None
    paper_ids: list[str] | None = None
    enable_rag: bool = True
    model: str | None = None
    thinking: bool = False
    reflection: bool = False


class FrozenTurnSnapshot(BaseModel):
    request_id: str
    session_id: str
    prompt: str
    selection: str
    written_context: str
    paper_ids: list[str]
    enable_rag: bool
    model_name: str
    thinking_enabled: bool
    reflection_enabled: bool = False
    recent_window: list[Any]
    history_summary: str
    frozen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    used_inputs: UsedInputs
