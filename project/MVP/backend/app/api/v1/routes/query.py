# 查询路由（新架构）：/api/v1/query
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models.query import AskRequest, RetrieveRequest
from app.models.base import ApiResponse
from app.modules.qa.service import QAService
from app.modules.retrieval.service import RetrievalService
import json

router = APIRouter(prefix="/query", tags=["query"])


def _get_qa_service() -> QAService:
    """获取 QA 服务实例."""
    return QAService()


def _get_retrieval_service() -> RetrievalService:
    """获取检索服务实例."""
    return RetrievalService()


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
            service = _get_qa_service()
            async for event in service.ask_stream_with_rag(
                session_id=request.session_id,
                query=request.query,
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
    service = _get_retrieval_service()
    results = await service.retrieve(
        query=request.query,
        top_k=request.top_k,
        resource_types=request.resource_types,
        selected_papers=request.selected_papers,
    )
    return ApiResponse(data={
        "query": request.query,
        "results": results["results"],
        "total": results["total"],
    })
