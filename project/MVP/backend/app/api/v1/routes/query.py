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
    """流式问答接口（SSE + RAG）

    ═════════════════════════════════════════════════════════════════════
    🔮 未来扩展：用户自选文献功能
    ═════════════════════════════════════════════════════════════════════

    前端可以通过以下参数控制检索范围：
    - resource_types: 资源类型过滤 ["paper", "video", "note", ...]
    - selected_papers: 用户选择的论文 ID 列表

    当前版本：这些参数已预留接口，暂未实现过滤逻辑。
    """

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

    # 🔮 调试：打印扩展参数
    resource_types_str = str(request.resource_types) if request.resource_types else "None"
    selected_papers_str = f"{len(request.selected_papers) if request.selected_papers else 0} papers"

    print(
        "[ASK] session_id=", request.session_id,
        "| query=", request.query[:80],
        "| written=", written_preview,
        "| selected=", selected_preview,
        "| prompt=", prompt_preview,
        "| resource_types=", resource_types_str,
        "| selected_papers=", selected_papers_str,
    )

    async def event_generator():
        try:
            async for event in qa_service_rag.ask_stream_with_rag(
                session_id=request.session_id,
                query=request.query,
                context=request.context,
                use_rag=True,
                resource_types=request.resource_types,
                selected_papers=request.selected_papers,
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
    """纯检索接口（非流式）

    ═════════════════════════════════════════════════════════════════════
    🔮 未来扩展：用户自选文献功能
    ═════════════════════════════════════════════════════════════════════

    支持通过 resource_types 和 selected_papers 控制检索范围。
    """
    results = await retrieve(
        request.query,
        request.top_k,
        resource_types=request.resource_types,
        selected_papers=request.selected_papers,
    )
    return ApiResponse(data={
        "query": request.query,
        "rewritten_query": request.query,
        "results": results,
    })
