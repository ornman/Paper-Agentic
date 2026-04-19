"""对话历史 API"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.deps import get_redis
from app.core.errors import AppError
from app.models.conversation import ChatMessage, ConversationResponse

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("/{session_id}")
async def get_conversation(session_id: str):
    redis = get_redis()
    try:
        messages = await redis.get_messages(session_id)
    except Exception as e:
        raise AppError(3001, f"Redis 不可用: {e}")

    return ConversationResponse(
        session_id=session_id,
        messages=[ChatMessage(**m) for m in messages],
    ).model_dump()


@router.delete("/{session_id}")
async def delete_conversation(session_id: str):
    redis = get_redis()
    try:
        await redis.delete_conversation(session_id)
    except Exception as e:
        raise AppError(3001, f"Redis 不可用: {e}")

    return {"status": "deleted", "session_id": session_id}
