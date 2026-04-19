"""
pytest 共享 fixtures

提供测试所需的临时存储实例和测试数据，所有 fixture 用完自动清理：

- temp_zvec:    临时 Zvec 向量库（tmp_path 隔离，测试结束自动销毁）
- temp_bm25:    临时 BM25 索引（tmp_path 隔离）
- temp_sqlite:  临时 SQLite 数据库（tmp_path 隔离，含建表）
- embed_client: EmbeddingClient 实例（用完自动 close，会调真实 API）
- sample_paper_id: 固定测试 ID "test_paper_001"
- sample_md_path:  真实论文 MD 路径（VR技术论文，78k chars，用于切块测试）
"""

import pytest


@pytest.fixture(scope="session")
def event_loop_policy():
    import asyncio
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def event_loop(event_loop_policy):
    loop = event_loop_policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_zvec(tmp_path):
    import shutil
    from app.stores.zvec_store import ZvecStore

    path = str(tmp_path / "zvec_db")
    store = ZvecStore(path, 1536)
    store.init()
    yield store
    store.close()


@pytest.fixture
def temp_bm25(tmp_path):
    from app.stores.bm25_store import BM25Store

    path = str(tmp_path / "bm25")
    store = BM25Store(path)
    store.init()
    yield store


@pytest.fixture
def temp_sqlite(tmp_path):
    from app.stores.sqlite_repo import SQLiteRepo

    path = str(tmp_path / "test.db")
    repo = SQLiteRepo(path)
    repo.init()
    yield repo


@pytest.fixture
async def embed_client():
    from app.clients.embedding_client import EmbeddingClient

    client = EmbeddingClient()
    yield client
    await client.close()


@pytest.fixture
def sample_paper_id():
    return "test_paper_001"


@pytest.fixture
def sample_md_path():
    return "./data/papers/85266a7a-f0aa-4ba1-bf55-43533448da12/full.md"
