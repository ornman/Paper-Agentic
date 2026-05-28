"""助手上下文 API 路由（written_context / selection / polling）"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.service_layer.schemas.assistant import (
    ContextState,
    EditorSelectionUpdate,
    PollingStartRequest,
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


@router.post("/polling/start")
async def start_polling(body: PollingStartRequest, request: Request):
    container = request.app.state.container
    if container.editor_context_store is None:
        raise HTTPException(status_code=503, detail="编辑器上下文存储不可用（Redis 未连接）")

    async def _wps_poll_fn():
        """占位 poll_fn — 实际应调用 WPS API 获取文档内容。
        当前架构下前端主动 push，此端点保留给后端轮询模式。"""
        return None

    container.editor_context_store.start_polling(
        poll_fn=_wps_poll_fn,
        session_id=body.session_id,
        interval=body.interval,
    )
    return {"status": "ok", "message": f"轮询已启动，间隔 {body.interval}s"}


@router.post("/polling/stop")
async def stop_polling(request: Request):
    container = request.app.state.container
    if container.editor_context_store is None:
        raise HTTPException(status_code=503, detail="编辑器上下文存储不可用（Redis 未连接）")

    container.editor_context_store.stop_polling()
    return {"status": "ok", "message": "轮询已停止"}
