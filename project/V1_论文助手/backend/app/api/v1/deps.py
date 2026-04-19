"""依赖注入：存储层单例访问"""

from __future__ import annotations

from app.stores.redis_cache import RedisCache
from app.stores.sqlite_repo import SQLiteRepo
from app.stores.zvec_store import ZvecStore
from app.stores.bm25_store import BM25Store

_sqlite: SQLiteRepo | None = None
_zvec: ZvecStore | None = None
_redis: RedisCache | None = None
_bm25: BM25Store | None = None


def init_deps(
    sqlite: SQLiteRepo,
    zvec: ZvecStore,
    redis: RedisCache,
    bm25: BM25Store,
) -> None:
    global _sqlite, _zvec, _redis, _bm25
    _sqlite = sqlite
    _zvec = zvec
    _redis = redis
    _bm25 = bm25


def get_sqlite() -> SQLiteRepo:
    assert _sqlite is not None, "SQLiteRepo not initialized"
    return _sqlite


def get_zvec() -> ZvecStore:
    assert _zvec is not None, "ZvecStore not initialized"
    return _zvec


def get_redis() -> RedisCache:
    assert _redis is not None, "RedisCache not initialized"
    return _redis


def get_bm25() -> BM25Store:
    assert _bm25 is not None, "BM25Store not initialized"
    return _bm25
