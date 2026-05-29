"""助手上下文 API 路由（written_context / selection / polling）"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.service_layer.schemas.assistant import (
    ContextState,
    EditorSelectionUpdate,
    PollingStartRequest,
    WrittenContextUpdate,
)

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.put("/written-context")
async def update_written_context(body: WrittenContextUpdate, request: Request):
    container = request.app.state.container
    existing = await container.editor_context_store.get(body.session_id) or {}
    existing["session_id"] = body.session_id
    existing["written_context"] = body.content
    await container.editor_context_store.put(existing)
    return {"status": "ok", "session_id": body.session_id}


@router.get("/written-context/{session_id}")
async def get_written_context(session_id: str, request: Request):
    container = request.app.state.container
    snapshot = await container.editor_context_store.get(session_id)
    snapshot = snapshot or {}
    return ContextState(
        session_id=session_id,
        written_context=snapshot.get("written_context", ""),
        selection=snapshot.get("selection", ""),
    )


@router.put("/selection")
async def update_selection(body: EditorSelectionUpdate, request: Request):
    container = request.app.state.container
    existing = await container.editor_context_store.get(body.session_id) or {}
    existing["session_id"] = body.session_id
    existing["selection"] = body.selection
    await container.editor_context_store.put(existing)
    return {"status": "ok", "session_id": body.session_id}


@router.get("/selection/{session_id}")
async def get_selection(session_id: str, request: Request):
    container = request.app.state.container
    snapshot = await container.editor_context_store.get(session_id)
    snapshot = snapshot or {}
    return ContextState(
        session_id=session_id,
        written_context=snapshot.get("written_context", ""),
        selection=snapshot.get("selection", ""),
    )


@router.post("/polling/start")
async def start_polling(body: PollingStartRequest, request: Request):
    container = request.app.state.container
    async def _wps_poll_fn():
        # 废弃：当前走前端 push 模式，后端不直接对接 WPS
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
    container.editor_context_store.stop_polling()
    return {"status": "ok", "message": "轮询已停止"}
