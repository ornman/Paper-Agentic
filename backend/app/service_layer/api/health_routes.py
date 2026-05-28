from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check(request: Request):
    return request.app.state.container.health()
