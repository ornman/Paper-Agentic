# API v1 路由聚合
from fastapi import APIRouter
from app.api.v1.routes import health, session, query, config, library

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(session.router)
api_router.include_router(query.router)
api_router.include_router(config.router)
api_router.include_router(library.router)
