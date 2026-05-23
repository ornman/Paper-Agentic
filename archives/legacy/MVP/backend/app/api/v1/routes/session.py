# 会话路由：/api/v1/session
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.models.session import SessionCreate, SessionResponse, SessionTitleUpdate, HistoryResponse, MessageResponse
from app.models.base import ApiResponse, PaginatedData
from app.repositories import sqlite_repo
from app.modules.session.service import SessionService

router = APIRouter(prefix="/session", tags=["session"])

# 获取 SessionService 实例
def _get_session_service() -> SessionService:
    """获取会话服务实例."""
    return SessionService()


@router.post("/", response_model=ApiResponse[SessionResponse])
async def create_session(request: SessionCreate):
    """创建会话"""
    session = sqlite_repo.create_session(request.title)
    count = sqlite_repo.get_message_count(session.id)
    data = SessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=count,
    )
    return ApiResponse(data=data)


@router.get("/", response_model=ApiResponse[PaginatedData[SessionResponse]])
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取会话列表（按更新时间倒序）"""
    sessions, total = sqlite_repo.list_sessions(page, page_size)
    items = [
        SessionResponse(
            id=s.id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=sqlite_repo.get_message_count(s.id),
        )
        for s in sessions
    ]
    return ApiResponse(data=PaginatedData(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    ))


@router.get("/{session_id}", response_model=ApiResponse[SessionResponse])
async def get_session(session_id: str):
    """获取会话详情"""
    session = sqlite_repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    count = sqlite_repo.get_message_count(session_id)
    return ApiResponse(data=SessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=count,
    ))


@router.put("/{session_id}/title", response_model=ApiResponse)
async def update_title(session_id: str, request: SessionTitleUpdate):
    """更新会话标题"""
    session = sqlite_repo.update_session_title(session_id, request.title)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ApiResponse(data={"id": session.id, "title": session.title})


@router.delete("/{session_id}", response_model=ApiResponse)
async def delete_session(session_id: str):
    """删除会话（级联删除消息）"""
    success = sqlite_repo.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ApiResponse(data=None, message="删除成功")


@router.get("/{session_id}/history", response_model=ApiResponse[HistoryResponse])
async def get_history(session_id: str):
    """获取会话历史消息"""
    session = sqlite_repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    session_service = _get_session_service()
    messages_raw = session_service.get_history(session_id)
    messages = [
        MessageResponse(
            id=m["id"],
            session_id=m["session_id"],
            role=m["role"],
            content=m["content"],
            sources=str(m["sources"]) if m["sources"] else None,
            created_at=m["created_at"],
        )
        for m in messages_raw
    ]
    return ApiResponse(data=HistoryResponse(session_id=session_id, messages=messages))


@router.delete("/{session_id}/history", response_model=ApiResponse)
async def clear_history(session_id: str):
    """清空会话历史"""
    session = sqlite_repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    session_service = _get_session_service()
    count = session_service.clear_history(session_id)
    return ApiResponse(data={"deleted": count}, message="历史已清空")
