"""依赖注入：存储层单例访问"""

from __future__ import annotations

from app.stores.sqlite_repo import SQLiteRepo
from app.stores.chroma_store import ChromaStore
from app.stores.bm25_store import BM25Store

_sqlite: SQLiteRepo | None = None
_chroma: ChromaStore | None = None
_bm25: BM25Store | None = None


def init_deps(
    sqlite: SQLiteRepo,
    chroma: ChromaStore,
    bm25: BM25Store,
) -> None:
    global _sqlite, _chroma, _bm25
    _sqlite = sqlite
    _chroma = chroma
    _bm25 = bm25


def get_sqlite() -> SQLiteRepo:
    assert _sqlite is not None, "SQLiteRepo not initialized"
    return _sqlite


def get_chroma() -> ChromaStore:
    assert _chroma is not None, "ChromaStore not initialized"
    return _chroma


def get_bm25() -> BM25Store:
    assert _bm25 is not None, "BM25Store not initialized"
    return _bm25
