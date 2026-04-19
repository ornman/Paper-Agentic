from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.deps import init_deps
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.stores.bm25_store import BM25Store
from app.stores.redis_cache import RedisCache
from app.stores.sqlite_repo import SQLiteRepo
from app.stores.zvec_store import ZvecStore

logger = logging.getLogger("paper-assistant")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    os.makedirs("./data/zvec_db", exist_ok=True)
    os.makedirs("./data/bm25_index", exist_ok=True)

    sqlite = SQLiteRepo("./data/app.db")
    sqlite.init()
    logger.info("SQLite initialized")

    zvec = ZvecStore(settings.zvec_data_dir, settings.embedding_dimensions)
    zvec.init()
    logger.info("Zvec initialized")

    redis = RedisCache(settings.redis_url, settings.redis_ttl)
    try:
        await redis.init()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning("Redis unavailable (%s) — features needing Redis will fail", e)

    bm25 = BM25Store("./data/bm25_index")
    bm25.init()
    logger.info("BM25 initialized")

    init_deps(sqlite=sqlite, zvec=zvec, redis=redis, bm25=bm25)

    yield

    zvec.close()
    await redis.close()


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    app = FastAPI(title="论文助手 V1", version="0.1.0", lifespan=lifespan)
    app.include_router(api_router)
    return app
