from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.service_layer.bootstrap.container import AppContainer
from app.service_layer.bootstrap.lifespan import build_lifespan
from app.service_layer.bootstrap.logging import configure_logging
from app.service_layer.config.settings import get_settings
from app.service_layer.api.exception_mapping import register_exception_handlers
from app.service_layer.api.router import api_router


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    container = AppContainer(settings)
    app = FastAPI(title="Paper Agentic Backend", version="0.2.0", lifespan=build_lifespan(container))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)
    return app
