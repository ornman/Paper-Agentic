# 配置路由：/api/v1/config
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.models.base import ApiResponse
from app.core.config import get_settings

router = APIRouter(prefix="/config", tags=["config"])


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
