"""模型发现 Schema"""

from __future__ import annotations

from pydantic import BaseModel


class ModelDiscoveryRequest(BaseModel):
    api_key: str
    api_url: str


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str | None = None
    support_thinking: bool | None = None


class ModelListResponse(BaseModel):
    models: list[ModelInfo]
