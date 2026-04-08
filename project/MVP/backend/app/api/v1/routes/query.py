# 查询路由：/api/v1/query
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models.query import AskRequest, RetrieveRequest
from app.models.base import ApiResponse
from app.services import qa_service_rag
from app.services.retrieval_service import retrieve
import json

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/ask")
async def ask(request: AskRequest) -> StreamingResponse:
    """流式问答接口（SSE + RAG）"""

    # 调试阶段验证：确保三类 context 字段确实被区分并到达后端。
    # 注意：这里只打印截断预览，避免把整篇正文刷屏。
    if request.context:
        written_preview = (request.context.written_content or "").replace("\n", " ").strip()[:80]
        selected_preview = (request.context.selected_text or "").replace("\n", " ").strip()[:80]
        prompt_preview = (request.context.prompt or "").replace("\n", " ").strip()[:80]
    else:
        written_preview = ""
        selected_preview = ""
        prompt_preview = ""

    print(
        "[ASK] session_id=", request.session_id,
        "| query=", request.query[:80],
        "| written=", written_preview,
        "| selected=", selected_preview,
        "| prompt=", prompt_preview,
    )

    async def event_generator():
        try:
            async for event in qa_service_rag.ask_stream_with_rag(
                session_id=request.session_id,
                query=request.query,
                context=request.context,
                use_rag=True,
            ):
                event_type = event["type"]
                event_data = json.dumps(event["data"], ensure_ascii=False)
                yield f"event: {event_type}\ndata: {event_data}\n\n"
        except Exception as e:
            error_data = json.dumps({"code": 9001, "message": str(e)}, ensure_ascii=False)
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/retrieve")
async def retrieve_endpoint(request: RetrieveRequest):
    """纯检索接口（非流式）"""
    results = await retrieve(request.query, request.top_k)
    return ApiResponse(data={
        "query": request.query,
        "rewritten_query": request.query,
        "results": results,
    })
