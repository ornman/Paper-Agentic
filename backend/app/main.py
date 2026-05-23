from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.deps import init_deps
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.stores.bm25_store import BM25Store
from app.stores.chroma_store import ChromaStore
from app.stores.sqlite_repo import SQLiteRepo

logger = logging.getLogger("paper-assistant")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    chroma_dir = Path(settings.chroma_data_dir)
    bm25_dir = Path(settings.bm25_data_dir)
    backup_dir = Path(settings.backup_dir)
    papers_dir = Path(settings.papers_dir)
    uploads_dir = Path(settings.uploads_dir)
    app_db_path = Path(settings.app_db_path)

    os.makedirs(chroma_dir, exist_ok=True)
    os.makedirs(bm25_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)
    os.makedirs(papers_dir, exist_ok=True)
    os.makedirs(uploads_dir, exist_ok=True)

    sqlite = SQLiteRepo(str(app_db_path))
    sqlite.init()
    logger.info("SQLite initialized")

    chroma = ChromaStore(str(chroma_dir), settings.embedding_dimensions)
    chroma.init()
    logger.info("Chroma initialized")

    bm25 = BM25Store(str(bm25_dir))
    bm25.init()
    logger.info("BM25 initialized")

    init_deps(sqlite=sqlite, chroma=chroma, bm25=bm25)

    yield

    chroma.close()


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    app = FastAPI(title="论文助手 V1", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app
