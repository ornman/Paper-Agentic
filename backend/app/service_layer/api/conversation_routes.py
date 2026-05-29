"""对话 API 路由"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.agent_layer.contracts.query import AskRequest
from app.data_layer.storage.sqlite_runtime._types import ConversationSession, utc_now_iso
from app.service_layer.schemas.conversation import (
    ChatRequest,
    ConversationMessageOut,
    ConversationSessionOut,
    RenameRequest,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationSessionOut])
async def list_sessions(request: Request):
    container = request.app.state.container
    sessions = container.conversation_repo.list_sessions(limit=50, offset=0)
    return [ConversationSessionOut(**s.__dict__) for s in sessions]


@router.post("", response_model=ConversationSessionOut)
async def create_session(request: Request):
    container = request.app.state.container
    session_id = uuid.uuid4().hex[:12]
    now = utc_now_iso()
    session = ConversationSession(session_id=session_id, title="新对话", created_at=now, updated_at=now)
    container.conversation_repo.upsert_session(session)
    return ConversationSessionOut(**session.__dict__)


@router.get("/{session_id}", response_model=ConversationSessionOut)
async def get_session(session_id: str, request: Request):
    container = request.app.state.container
    session = container.conversation_repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ConversationSessionOut(**session.__dict__)


@router.delete("/{session_id}")
async def delete_session(session_id: str, request: Request):
    container = request.app.state.container
    session = container.conversation_repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    container.conversation_repo.delete_session(session_id)
    return {"status": "ok", "message": "会话已删除"}


@router.put("/{session_id}/title", response_model=ConversationSessionOut)
async def rename_session(session_id: str, body: RenameRequest, request: Request):
    """重命名会话"""
    container = request.app.state.container
    ok = container.conversation_repo.rename_session(session_id, body.title)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    session = container.conversation_repo.get_session(session_id)
    return ConversationSessionOut(**session.__dict__)


@router.get("/search")
async def search_conversations(request: Request, q: str = "", limit: int = 20):
    """搜索会话（标题）和消息（内容）"""
    if not q.strip():
        return {"sessions": [], "messages": []}

    container = request.app.state.container
    sessions = container.conversation_repo.search_sessions(q, limit=limit)
    messages = container.conversation_repo.search_messages(q, limit=limit)

    return {
        "sessions": [ConversationSessionOut(**s.__dict__) for s in sessions],
        "messages": [ConversationMessageOut(**m.__dict__) for m in messages],
    }


@router.get("/{session_id}/messages", response_model=list[ConversationMessageOut])
async def list_messages(session_id: str, request: Request, limit: int = 50):
    container = request.app.state.container
    messages = container.conversation_repo.get_messages(session_id, limit=limit)
    return [ConversationMessageOut(**m.__dict__) for m in messages]


@router.post("/chat")
async def chat(body: ChatRequest, request: Request):
    """对话入口 — 转发到 TurnRunner（与 /api/v1/query 共享同一套 Agent 编排）"""
    from app.service_layer.api.query_routes import _build_runner

    session_id = body.session_id or uuid.uuid4().hex[:12]
    ask_req = AskRequest(
        session_id=session_id,
        prompt=body.message,
        paper_ids=body.paper_ids,
        enable_rag=True,
    )

    runner = _build_runner(request)

    async def event_stream():
        async for frame in runner.run(ask_req):
            yield frame

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
