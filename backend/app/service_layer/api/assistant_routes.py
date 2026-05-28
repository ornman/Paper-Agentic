"""助手上下文 API 路由（written_context / selection）"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from app.service_layer.schemas.assistant import (
    ContextState,
    EditorSelectionUpdate,
    WrittenContextUpdate,
)

logger = logging.getLogger("paper-assistant")

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.put("/written-context")
async def update_written_context(body: WrittenContextUpdate, request: Request):
    container = request.app.state.container
    if container.editor_context_store is None:
        return {"status": "degraded", "message": "Redis 不可用，上下文未持久化"}
    existing = await container.editor_context_store.get(body.session_id) or {}
    existing["session_id"] = body.session_id
    existing["written_context"] = body.content
    await container.editor_context_store.put(existing)
    return {"status": "ok", "session_id": body.session_id}


@router.get("/written-context/{session_id}")
async def get_written_context(session_id: str, request: Request):
    container = request.app.state.container
    if container.editor_context_store is None:
        return ContextState(session_id=session_id, written_context="", selection="")
    snapshot = await container.editor_context_store.get(session_id)
    content = snapshot.get("written_context", "") if snapshot else ""
    return ContextState(session_id=session_id, written_context=content, selection="")


@router.put("/selection")
async def update_selection(body: EditorSelectionUpdate, request: Request):
    container = request.app.state.container
    if container.editor_context_store is None:
        return {"status": "degraded", "message": "Redis 不可用，选区未持久化"}
    existing = await container.editor_context_store.get(body.session_id) or {}
    existing["session_id"] = body.session_id
    existing["selection"] = body.selection
    await container.editor_context_store.put(existing)
    return {"status": "ok", "session_id": body.session_id}


@router.get("/selection/{session_id}")
async def get_selection(session_id: str, request: Request):
    container = request.app.state.container
    if container.editor_context_store is None:
        return ContextState(session_id=session_id, written_context="", selection="")
    snapshot = await container.editor_context_store.get(session_id)
    selection = snapshot.get("selection", "") if snapshot else ""
    return ContextState(session_id=session_id, written_context="", selection=selection)
