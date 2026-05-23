"""轮询同步 API（WPS 插件定期推送用户上下文）"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/poll", tags=["poll"])

_poll_cache: dict[str, str] = {}


class PollSyncRequest(BaseModel):
    session_id: str
    content: str


@router.post("/sync")
async def poll_sync(req: PollSyncRequest):
    """保存 WPS 轮询内容到内存"""
    _poll_cache[req.session_id] = req.content
    return {"status": "ok", "session_id": req.session_id}


@router.get("/{session_id}")
async def poll_get(session_id: str):
    """获取 WPS 轮询内容"""
    content = _poll_cache.get(session_id, "")
    return {"session_id": session_id, "content": content}
