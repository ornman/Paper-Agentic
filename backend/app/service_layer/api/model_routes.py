"""模型发现 API"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from openai import AsyncOpenAI

from app.service_layer.schemas.model import ModelDiscoveryRequest, ModelInfo, ModelListResponse

logger = logging.getLogger("paper-assistant")

router = APIRouter(tags=["models"])


@router.post("/models", response_model=ModelListResponse)
async def discover_models(body: ModelDiscoveryRequest):
    try:
        client = AsyncOpenAI(api_key=body.api_key, base_url=body.api_url, timeout=15.0)
        models_resp = await client.models.list()
        await client.close()

        models = [
            ModelInfo(
                id=m.id,
                name=m.id,
                provider=getattr(m, "owned_by", None),
            )
            for m in models_resp.data
        ]
        return ModelListResponse(models=models)
    except Exception as e:
        logger.warning("模型列表获取失败: %s", e)
        raise HTTPException(status_code=502, detail=f"模型列表获取失败: {e}")
