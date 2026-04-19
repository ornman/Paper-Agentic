"""轮询同步 API（WPS 插件定期推送用户上下文）"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1.deps import get_redis
from app.core.errors import AppError

router = APIRouter(prefix="/poll", tags=["poll"])


class PollSyncRequest(BaseModel):
    session_id: str
    content: str


@router.post("/sync")
async def poll_sync(req: PollSyncRequest):
    """保存 WPS 轮询内容到 Redis"""
    redis = get_redis()
    try:
        await redis.set_poll_cache(req.session_id, req.content)
    except Exception as e:
        raise AppError(3001, f"Redis 不可用: {e}")

    return {"status": "ok", "session_id": req.session_id}
