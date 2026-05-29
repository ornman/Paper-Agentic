from __future__ import annotations

from fastapi import APIRouter

from app.service_layer.api.assistant_routes import router as assistant_router
from app.service_layer.api.config_routes import router as config_router
from app.service_layer.api.conversation_routes import router as conversation_router
from app.service_layer.api.health_routes import router as health_router
from app.service_layer.api.import_routes import router as import_router
from app.service_layer.api.library_routes import router as library_router
from app.service_layer.api.model_routes import router as model_router
from app.service_layer.api.papers_routes import router as papers_router
from app.service_layer.api.query_routes import router as query_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(config_router)
api_router.include_router(library_router)
api_router.include_router(papers_router)
api_router.include_router(import_router)
api_router.include_router(model_router)
api_router.include_router(conversation_router)
api_router.include_router(assistant_router)
api_router.include_router(query_router)
