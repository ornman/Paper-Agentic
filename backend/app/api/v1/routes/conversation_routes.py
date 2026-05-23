"""对话历史 API"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text as sa_text

from app.api.v1.deps import get_sqlite
from app.core.errors import AppError
from app.models.conversation import ChatMessage, ConversationResponse

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("/list")
async def list_conversations(limit: int = 20, offset: int = 0):
    """获取所有对话会话列表（从 SQLite）"""
    sqlite = get_sqlite()
    try:
        with sqlite.get_session() as session:
            rows = session.execute(sa_text("""
                SELECT session_id, COUNT(*) as msg_count,
                       MAX(created_at) as last_active,
                       MIN(CASE WHEN role = 'user' THEN content END) as preview
                FROM conversations
                GROUP BY session_id
                ORDER BY last_active DESC
                LIMIT :limit OFFSET :offset
            """), {"limit": limit, "offset": offset}).fetchall()

            return [{
                "session_id": row[0],
                "msg_count": row[1],
                "last_active": row[2],
                "preview": (row[3] or "")[:60],
            } for row in rows]
    except Exception as e:
        raise AppError(3002, f"查询对话列表失败: {e}")


@router.get("/{session_id}")
async def get_conversation(session_id: str):
    """获取单个对话的完整历史（从 SQLite）"""
    sqlite = get_sqlite()

    try:
        with sqlite.get_session() as session:
            rows = session.execute(sa_text("""
                SELECT role, content, created_at
                FROM conversations
                WHERE session_id = :sid
                ORDER BY created_at ASC
            """), {"sid": session_id}).fetchall()

            if rows:
                return ConversationResponse(
                    session_id=session_id,
                    messages=[ChatMessage(role=r[0], content=r[1]) for r in rows],
                ).model_dump()
    except Exception as e:
        raise AppError(3002, f"查询对话历史失败: {e}")

    return ConversationResponse(
        session_id=session_id,
        messages=[],
    ).model_dump()


@router.delete("")
async def delete_all_conversations():
    """删除全部对话会话"""
    try:
        sqlite = get_sqlite()
        with sqlite.get_session() as session:
            session.execute(sa_text("DELETE FROM conversations"))
            session.commit()
    except Exception as e:
        raise AppError(3002, f"删除全部对话失败: {e}")

    return {"status": "deleted", "scope": "all"}


@router.delete("/{session_id}")
async def delete_conversation(session_id: str):
    """删除对话会话"""
    try:
        sqlite = get_sqlite()
        with sqlite.get_session() as session:
            session.execute(sa_text(
                "DELETE FROM conversations WHERE session_id = :sid"
            ), {"sid": session_id})
            session.commit()
    except Exception as e:
        raise AppError(3002, f"删除对话失败: {e}")

    return {"status": "deleted", "session_id": session_id}
