from fastapi import APIRouter

from .routes.health_routes import router as health_router
from .routes.import_routes import router as import_router
from .routes.query_routes import router as query_router
from .routes.paper_routes import router as paper_router
from .routes.conversation_routes import router as conversation_router
from .routes.poll_routes import router as poll_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(import_router)
api_router.include_router(query_router)
api_router.include_router(paper_router)
api_router.include_router(conversation_router)
api_router.include_router(poll_router)
