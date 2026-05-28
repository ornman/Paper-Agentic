from __future__ import annotations

from pydantic import BaseModel


class UsedInputs(BaseModel):
    prompt: float = 0.0
    selection: float = 0.0
    written_context: float = 0.0
    rag_evidence: float = 0.0
