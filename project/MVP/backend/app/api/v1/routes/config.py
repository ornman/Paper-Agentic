# 配置路由：/api/v1/config
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.models.base import ApiResponse
from app.core.config import get_settings
from app.core.logging_config import export_logs_to_desktop, get_logger

router = APIRouter(prefix="/config", tags=["config"])
logger = get_logger()


class LLMConfigUpdate(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class RetrievalConfigUpdate(BaseModel):
    vector_top_k: Optional[int] = None
    bm25_top_k: Optional[int] = None
    final_top_k: Optional[int] = None
    rrf_k: Optional[int] = None


class ConfigTestRequest(BaseModel):
    test_type: str  # "llm" | "embedding" | "rerank"


@router.get("/", response_model=ApiResponse)
async def get_config():
    """获取当前配置（敏感字段脱敏）"""
    s = get_settings()

    def mask_key(key: str) -> str:
        """脱敏 API Key，保留前4位和后4位"""
        if not key or len(key) < 8:
            return "" if not key else "***"
        return key[:4] + "***" + key[-4:]

    return ApiResponse(data={
        "llm": {
            "api_key": mask_key(s.llm_api_key),
            "base_url": s.llm_base_url,
            "model": s.llm_model,
            "temperature": s.llm_temperature,
            "max_tokens": s.llm_max_tokens,
        },
        "retrieval": {
            "vector_top_k": s.retrieval_vector_top_k,
            "bm25_top_k": s.retrieval_bm25_top_k,
            "final_top_k": s.retrieval_final_top_k,
            "rrf_k": s.retrieval_rrf_k,
        },
    })


@router.post("/test", response_model=ApiResponse)
async def test_config(request: ConfigTestRequest):
    """
    测试指定组件的连接性
    MVP 阶段仅测试 LLM
    """
    import time
    s = get_settings()

    if request.test_type == "llm":
        if not s.llm_api_key:
            return ApiResponse(
                code=1001,
                data={"success": False, "latency_ms": 0, "error": "LLM API Key 未配置"},
                message="配置缺失",
            )
        try:
            from app.clients.llm_client import LLMClient
            start = time.time()
            llm = LLMClient()
            result = await llm.chat([{"role": "user", "content": "hi"}])
            latency = int((time.time() - start) * 1000)
            return ApiResponse(data={"success": True, "latency_ms": latency, "error": None})
        except Exception as e:
            return ApiResponse(
                code=1002,
                data={"success": False, "latency_ms": 0, "error": str(e)},
                message="连接失败",
            )
    else:
        return ApiResponse(
            code=9001,
            data={"success": False, "latency_ms": 0, "error": f"暂不支持测试类型: {request.test_type}"},
            message="暂未实现",
        )


@router.get("/models", response_model=ApiResponse)
async def get_models():
    """返回推荐的模型列表"""
    return ApiResponse(data={
        "llm_models": [
            "deepseek-chat",
            "deepseek-reasoner",
            "glm-4-flash",
            "glm-4-air",
            "Qwen/Qwen3-7B",
            "Qwen/Qwen3-14B",
        ],
        "embedding_models": [
            "Qwen/Qwen3-Embedding-8B",
            "BAAI/bge-m3",
        ],
        "rerank_models": [
            "Qwen/Qwen3-Reranker-8B",
            "Qwen/Qwen3-Reranker-4B",
            "BAAI/bge-reranker-v2-m3",
        ],
    })


@router.post("/export_logs", response_model=ApiResponse)
async def export_logs(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """导出系统日志到桌面.

    Args:
        start_date: 开始日期（YYYY-MM-DD），可选
        end_date: 结束日期（YYYY-MM-DD），可选

    Returns:
        导出结果
    """
    try:
        export_path = export_logs_to_desktop(start_date, end_date)
        logger.info(f"日志导出成功: {export_path}")
        return ApiResponse(
            data={
                "export_path": export_path,
                "start_date": start_date,
                "end_date": end_date,
            },
            message="日志导出成功",
        )
    except Exception as e:
        logger.error(f"日志导出失败: {e}")
        return ApiResponse(
            code=9001,
            data={"error": str(e)},
            message="日志导出失败",
        )


@router.post("/reload", response_model=ApiResponse)
async def reload_config():
    """重新加载配置.

    清除配置缓存并重新加载环境变量。
    注意：这不会影响已创建的单例对象（如客户端实例）。

    Returns:
        重新加载后的配置
    """
    try:
        from app.core.config import reload_settings
        new_settings = reload_settings()

        logger.info("配置已重新加载")
        return ApiResponse(
            data={
                "environment": new_settings.environment,
                "debug": new_settings.debug,
                "timestamp": new_settings.model_dump(exclude={"api_key", "embedding_api_key", "rerank_api_key"}),
            },
            message="配置重新加载成功",
        )
    except Exception as e:
        logger.error(f"配置重新加载失败: {e}")
        return ApiResponse(
            code=9001,
            data={"error": str(e)},
            message="配置重新加载失败",
        )
