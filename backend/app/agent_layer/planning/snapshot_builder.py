from __future__ import annotations

import uuid

from ..contracts.query import AskRequest, FrozenTurnSnapshot
from ..contracts.used_inputs import UsedInputs


def build_snapshot(
    request: AskRequest,
    editor_context: dict | None,
    recent_window: list,
    history_summary: str,
) -> FrozenTurnSnapshot:
    selection = request.selection or ""
    written_context = _extract_written_context(editor_context)
    prompt = request.prompt

    used_inputs = _compute_weights(prompt, selection, written_context)

    return FrozenTurnSnapshot(
        request_id=uuid.uuid4().hex,
        session_id=request.session_id,
        prompt=prompt,
        selection=selection,
        written_context=written_context,
        paper_ids=request.paper_ids or [],
        enable_rag=request.enable_rag,
        model_name=request.model or "",
        thinking_enabled=request.thinking,
        reflection_enabled=request.reflection,
        recent_window=recent_window,
        history_summary=history_summary,
        used_inputs=used_inputs,
    )


def _extract_written_context(editor_context: dict | None) -> str:
    if not editor_context:
        return ""
    return editor_context.get("draft", "") or editor_context.get("content", "") or ""


def _compute_weights(
    prompt: str,
    selection: str,
    written_context: str,
) -> UsedInputs:
    has_prompt = bool(prompt.strip())
    has_selection = bool(selection.strip())
    has_written = bool(written_context.strip())

    if has_written and has_selection and has_prompt:
        return UsedInputs(prompt=0.5, selection=0.3, written_context=0.2)

    if has_written and has_selection:
        return UsedInputs(selection=0.7, written_context=0.3)

    if has_written:
        return UsedInputs(written_context=1.0)

    return UsedInputs(prompt=1.0)
