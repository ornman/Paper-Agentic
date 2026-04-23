"""问答 API 路由"""

from __future__ import annotations

import json

from fastapi import APIRouter
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from app.models.query import QueryRequest
from app.pipelines.retrieval.service import QAService

router = APIRouter(prefix="/query", tags=["query"])

_qa_service: QAService | None = None


def _get_qa() -> QAService:
    global _qa_service
    if _qa_service is None:
        _qa_service = QAService()
    return _qa_service


@router.post("")
async def query(req: QueryRequest):
    """SSE 流式问答"""
    qa = _get_qa()

    async def event_generator():
        async for event in qa.query(
            session_id=req.session_id,
            prompt=req.prompt,
            selection=req.selection,
            draft=req.draft,
            paper_ids=req.paper_ids,
            enable_rag=req.enable_rag,
        ):
            event_type = event.get("event", "chunk")
            data = json.dumps(event.get("data", {}), ensure_ascii=False)
            yield f"event: {event_type}\ndata: {data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


class TitleRequest(BaseModel):
    message: str


@router.post("/generate-title")
async def generate_title(req: TitleRequest):
    """根据首条消息生成对话标题"""
    qa = _get_qa()
    try:
        title = await qa.generate_title(req.message)
        return {"title": title}
    except Exception as e:
        return {"title": req.message[:20]}
