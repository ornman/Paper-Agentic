# 健康检查路由：/api/v1/health
from fastapi import APIRouter
from app.models.base import ApiResponse
from app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", response_model=ApiResponse)
async def health_check():
    """健康检查，返回服务状态和组件可用性"""
    settings = get_settings()

    # 检查各组件配置是否就绪
    components = {
        "llm": "ok" if settings.llm_api_key else "no_api_key",
        "embedding": "ok" if settings.embedding_api_key else "no_api_key",
        "rerank": "ok" if settings.rerank_api_key else "no_api_key",
        "vector_db": "ok",   # ChromaDB 本地，始终可用
        "sqlite": "ok",      # SQLite 本地，始终可用
    }

    # 只要 LLM 可用就认为服务正常（MVP 阶段）
    status = "ok" if settings.llm_api_key else "degraded"

    return ApiResponse(data={
        "status": status,
        "version": "1.0.0-mvp",
        "components": components,
    })
