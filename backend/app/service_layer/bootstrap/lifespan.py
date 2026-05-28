from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.service_layer.bootstrap.container import AppContainer


def build_lifespan(container: AppContainer):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await container.initialize()
        app.state.container = container
        yield
        await container.close()

    return lifespan
