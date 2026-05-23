# Task 5: 双索引模式与维度守卫测试
# 这里严格先写测试，再补实现。
# 当前测试只覆盖 Task 5 的最小行为，不提前触碰 Task 6+ 的场景路由与 QA。

from __future__ import annotations

import pickle
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.core.errors import IndexingError
from app.modules.ingestion.dto import CleanedBlock, CleanedDocument


class _FakeEmbeddingClient:
    """假的 embedding 客户端。

    这个假客户端只暴露 Task 5 真正需要的最小契约：
    1. model_name
    2. dimensions
    3. async embed()

    这样测试可以精确验证“写入前契约守卫”与“索引写入结果”，
    而不会被真实网络请求绑死。
    """

    def __init__(self, *, model_name: str, dimensions: int) -> None:
        self.model_name = model_name
        self.dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """按输入数量返回固定长度向量。"""
        return [self._build_vector(index) for index, _ in enumerate(texts)]

    def _build_vector(self, seed: int) -> list[float]:
        """构造稳定的 1536 维假向量。

        这里不追求语义真实性，只追求：
        1. 长度稳定
        2. 每个 chunk 的向量不同
        3. 便于测试 Chroma 真正完成写入
        """
        return [float(seed + 1)] * self.dimensions


class _BadDimensionEmbeddingClient(_FakeEmbeddingClient):
    """故意返回错误维度的 embedding，用于复现重建中途失败。"""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """返回比声明维度更短的向量，触发输出维度校验失败。"""
        return [[1.0] * (self.dimensions - 1) for _ in texts]


class _BrokenBM25Repo:
    """故意在 BM25 写入阶段抛错，用于验证 Chroma 回滚。"""

    def __init__(self) -> None:
        self._all_chunks = []

    def upsert_chunks(self, chunks):  # noqa: ANN001
        """模拟 BM25 落盘失败。"""
        raise RuntimeError("bm25 write failed")

    def delete_document(self, document_id: str) -> int:
        """测试里不需要真正删除 BM25。"""
        return 0

    def snapshot(self) -> list:
        """返回最小快照接口，兼容 service 的补偿逻辑。"""
        return list(self._all_chunks)

    def restore(self, chunks) -> int:  # noqa: ANN001
        """恢复最小快照接口，兼容 service 的补偿逻辑。"""
        self._all_chunks = list(chunks)
        return len(self._all_chunks)

    def get_chunks_by_ids(self, chunk_ids: list[str]):  # noqa: ANN001
        """兼容 service.attach_parent_context 的最小接口。"""
        return []

    def count(self, document_id: str | None = None, *, searchable_only: bool = False) -> int:
        """测试里让它表现为空索引。"""
        return 0


class _FakeAsyncClient:
    """假的 httpx AsyncClient，用于捕获 embedding 请求体。"""

    captured_json: dict | None = None

    def __init__(self, timeout: float | None = None, **kwargs) -> None:  # noqa: ANN003
        """兼容真实 AsyncClient 构造参数。

        这里显式接收 timeout，原因不是测试真的要用它，
        而是为了和生产代码的调用签名保持兼容，避免测试夹带无关失败。
        """
        self.timeout = timeout
        self.kwargs = kwargs

    async def __aenter__(self) -> "_FakeAsyncClient":
        """支持 async with 语法。"""
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        """退出上下文时不做任何事。"""
        return None

    async def post(self, url: str, *, headers: dict, json: dict):
        """记录请求体，并返回最小可用响应。"""
        _FakeAsyncClient.captured_json = json
        embedding_dimensions = int(json["dimensions"])
        inputs = json["input"]
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "data": [
                    {
                        "index": index,
                        "embedding": [float(index + 1)] * embedding_dimensions,
                    }
                    for index, _ in enumerate(inputs)
                ]
            },
        )


class _RecordingChromaRepo:
    """记录型假的 Chroma 仓储，用于验证失败前不应发生写入。"""

    def __init__(self) -> None:
        self.upsert_called = False

    def upsert_chunks(self, chunks):  # noqa: ANN001
        self.upsert_called = True


class _RecordingBM25Repo:
    """记录型假的 BM25 仓储，用于验证失败前不应发生写入。"""

    def __init__(self) -> None:
        self.upsert_called = False

    def upsert_chunks(self, chunks):  # noqa: ANN001
        self.upsert_called = True



def _make_token_text(prefix: str, token_count: int) -> str:
    """构造稳定的空格分词文本。

    这里故意用空格分隔 token，
    是为了让测试对 chunk 长度与重叠的断言足够稳定，
    不依赖第三方 tokenizer 的细节波动。
    """
    return " ".join(f"{prefix}_{index:04d}" for index in range(token_count))



def _tokenize_for_test(text: str) -> list[str]:
    """测试侧 token 切分规则。"""
    return [token for token in text.split(" ") if token]



def _build_cleaned_document(*, document_id: str, index_mode: str, block_token_counts: list[int]) -> CleanedDocument:
    """构造清洗后的测试文档。"""
    blocks = [
        CleanedBlock(
            block_id=f"{document_id}-block-{index}",
            page=index,
            text=_make_token_text(f"{document_id}_p{index}", token_count),
        )
        for index, token_count in enumerate(block_token_counts, start=1)
    ]
    return CleanedDocument(
        document_id=document_id,
        title=f"标题-{document_id}",
        file_path=f"D:/papers/{document_id}.pdf",
        index_mode=index_mode,
        blocks=blocks,
        raw_block_count=len(blocks),
        cleaned_block_count=len(blocks),
        removed_block_count=0,
    )



def _build_cleaned_document_from_texts(*, document_id: str, index_mode: str, block_texts: list[str]) -> CleanedDocument:
    """直接用原始块文本构造清洗文档。

    这个辅助函数只服务于回归测试，原因是：
    1. 现有 _build_cleaned_document() 默认会人为插入空格 token。
    2. 这会掩盖“整段中文无空格被吞成 1 个 token”的真实故障。
    3. 所以这里必须允许测试直接喂入无空格正文，才能稳定复现并锁住修复。
    """
    blocks = [
        CleanedBlock(
            block_id=f"{document_id}-block-{index}",
            page=index,
            text=block_text,
        )
        for index, block_text in enumerate(block_texts, start=1)
    ]
    return CleanedDocument(
        document_id=document_id,
        title=f"标题-{document_id}",
        file_path=f"D:/papers/{document_id}.pdf",
        index_mode=index_mode,
        blocks=blocks,
        raw_block_count=len(blocks),
        cleaned_block_count=len(blocks),
        removed_block_count=0,
    )



def _use_temp_index_storage(monkeypatch) -> Path:  # noqa: ANN001
    """切换到项目内临时索引目录，避免同步盘临时目录清理问题。"""
    backend_root = Path(__file__).resolve().parents[2]
    temp_dir = backend_root / "data" / "test-temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    run_dir = temp_dir / f"indexing-task5-{uuid.uuid4()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.chdir(run_dir)
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(run_dir / "chroma"))
    monkeypatch.setenv("BM25_INDEX_PATH", str(run_dir / "bm25-index.json"))
    get_settings.cache_clear()
    return run_dir



def test_brute_index_mode_splits_into_overlapped_chunks_with_token_bounds():
    """brute 模式必须产出 500~1000 token 的重叠切块。"""
    from app.modules.indexing.chunkers.brute import build_brute_index

    cleaned_document = _build_cleaned_document(
        document_id="doc-brute",
        index_mode="brute",
        block_token_counts=[1600],
    )

    result = build_brute_index(cleaned_document)

    assert result.mode == "brute"
    assert len(result.chunks) >= 2

    token_counts = [_tokenize_for_test(chunk.text) for chunk in result.chunks]
    assert all(500 <= len(tokens) <= 1000 for tokens in token_counts)
    assert token_counts[0][-100:] == token_counts[1][:100]



def test_brute_index_mode_splits_continuous_chinese_text_without_spaces():
    """连续中文正文即使没有空格，也必须稳定切成 500~1000 token 窗口。"""
    from app.modules.indexing.chunkers.brute import build_brute_index, tokenize_text

    cleaned_document = _build_cleaned_document_from_texts(
        document_id="doc-brute-cn",
        index_mode="brute",
        block_texts=["中" * 1600],
    )

    result = build_brute_index(cleaned_document)

    assert len(tokenize_text(cleaned_document.blocks[0].text)) == 1600
    assert len(result.chunks) >= 2

    chunk_token_counts = [len(tokenize_text(chunk.text)) for chunk in result.chunks]
    assert all(500 <= token_count <= 1000 for token_count in chunk_token_counts)



def test_brute_index_mode_keeps_continuous_chinese_chunk_text_without_inserted_spaces():
    """连续中文切块后，chunk.text 不能退化成逐字空格串。"""
    from app.modules.indexing.chunkers.brute import build_brute_index

    cleaned_document = _build_cleaned_document_from_texts(
        document_id="doc-brute-cn-display",
        index_mode="brute",
        block_texts=["人工智能推动社会发展"],
    )

    result = build_brute_index(cleaned_document)

    assert len(result.chunks) == 1
    assert result.chunks[0].text == "人工智能推动社会发展"
    assert result.chunks[0].text != "人 工 智 能 推 动 社 会 发 展"



def test_parent_child_index_mode_builds_parent_and_child_records():
    """parent_child 模式必须同时产出父块与子块，并支持子块回挂父块。"""
    from app.modules.indexing.chunkers.parent_child import (
        attach_parent_blocks,
        build_parent_child_index,
    )

    cleaned_document = _build_cleaned_document(
        document_id="doc-parent-child",
        index_mode="parent_child",
        block_token_counts=[600, 650, 620],
    )

    result = build_parent_child_index(cleaned_document)
    attached_parents = attach_parent_blocks(result, [result.child_chunks[0].chunk_id])

    parent_ids = {parent.chunk_id for parent in result.parent_blocks}

    assert result.parent_blocks
    assert result.child_chunks
    assert all(child.parent_chunk_id in parent_ids for child in result.child_chunks)
    assert len(attached_parents) == 1
    assert attached_parents[0].chunk_id == result.child_chunks[0].parent_chunk_id
    assert result.child_chunks[0].text in attached_parents[0].text


@pytest.mark.asyncio
async def test_indexing_service_rejects_wrong_embedding_contract_before_write():
    """写入前必须拦截错误的 embedding 模型与维度，避免污染索引。"""
    from app.modules.indexing.service import IndexingService

    cleaned_document = _build_cleaned_document(
        document_id="doc-contract-guard",
        index_mode="brute",
        block_token_counts=[800],
    )

    chroma_repo = _RecordingChromaRepo()
    bm25_repo = _RecordingBM25Repo()

    with pytest.raises(IndexingError, match="Qwen/Qwen3-Embedding-8B"):
        await IndexingService(
            embedding_client=_FakeEmbeddingClient(model_name="BAAI/bge-m3", dimensions=1536),
            chroma_repo=chroma_repo,
            bm25_repo=bm25_repo,
        ).index_document(cleaned_document)

    assert chroma_repo.upsert_called is False
    assert bm25_repo.upsert_called is False

    with pytest.raises(IndexingError, match="1536"):
        await IndexingService(
            embedding_client=_FakeEmbeddingClient(model_name="Qwen/Qwen3-Embedding-8B", dimensions=1024),
            chroma_repo=_RecordingChromaRepo(),
            bm25_repo=_RecordingBM25Repo(),
        ).index_document(cleaned_document)


@pytest.mark.asyncio
async def test_indexing_service_writes_dual_indexes_and_deletes_document(monkeypatch):
    """索引服务必须同时写入 Chroma 与 BM25，并支持按 document_id 同步删除。"""
    _use_temp_index_storage(monkeypatch)

    from app.modules.indexing.service import IndexingService

    cleaned_document = _build_cleaned_document(
        document_id="doc-write-delete",
        index_mode="parent_child",
        block_token_counts=[700, 720],
    )

    service = IndexingService(
        embedding_client=_FakeEmbeddingClient(
            model_name="Qwen/Qwen3-Embedding-8B",
            dimensions=1536,
        )
    )

    result = await service.index_document(cleaned_document)
    bm25_hits = service.bm25_repo.query("doc-write-delete_p1_0001", top_k=3)
    attached_parents = service.attach_parent_context([bm25_hits[0].chunk_id])

    assert result.index_mode == "parent_child"
    assert result.vector_count >= 1
    assert result.bm25_count >= 1
    assert service.chroma_repo.count(document_id=cleaned_document.document_id) == result.vector_count
    assert service.bm25_repo.count(document_id=cleaned_document.document_id, searchable_only=True) == result.bm25_count
    assert bm25_hits
    assert attached_parents
    assert attached_parents[0].document_id == cleaned_document.document_id
    assert attached_parents[0].node_kind == "parent"

    delete_result = service.delete_document(cleaned_document.document_id)

    assert delete_result.document_id == cleaned_document.document_id
    assert delete_result.deleted_vector_count == result.vector_count
    assert delete_result.deleted_bm25_count >= result.bm25_count
    assert service.chroma_repo.count(document_id=cleaned_document.document_id) == 0
    assert service.bm25_repo.count(document_id=cleaned_document.document_id) == 0


@pytest.mark.asyncio
async def test_delete_document_keeps_old_indexes_when_bm25_delete_save_fails(monkeypatch):
    """删除路径上只要 BM25 删除落盘失败，旧的 Chroma 与 BM25 都必须保留。"""
    _use_temp_index_storage(monkeypatch)

    from app.modules.indexing.bm25_repo import BM25Repo
    from app.modules.indexing.chroma_repo import ChromaRepo
    from app.modules.indexing.service import IndexingService

    cleaned_document = _build_cleaned_document(
        document_id="doc-delete-rollback",
        index_mode="brute",
        block_token_counts=[800],
    )

    chroma_repo = ChromaRepo()
    seed_service = IndexingService(
        embedding_client=_FakeEmbeddingClient(
            model_name="Qwen/Qwen3-Embedding-8B",
            dimensions=1536,
        ),
        chroma_repo=chroma_repo,
        bm25_repo=BM25Repo(),
    )
    first_result = await seed_service.index_document(cleaned_document)

    before_vector_count = chroma_repo.count(document_id=cleaned_document.document_id)
    before_bm25_count = seed_service.bm25_repo.count(document_id=cleaned_document.document_id)
    assert before_vector_count == first_result.vector_count
    assert before_bm25_count >= first_result.bm25_count

    class _FailingDeleteSaveBM25Repo(BM25Repo):
        """故意让删除阶段的 save 失败，用来锁住半删除回归。"""

        def save(self) -> None:
            """模拟 BM25 删除落盘失败。"""
            raise RuntimeError("bm25 save failed during delete")

    failing_service = IndexingService(
        embedding_client=_FakeEmbeddingClient(
            model_name="Qwen/Qwen3-Embedding-8B",
            dimensions=1536,
        ),
        chroma_repo=chroma_repo,
        bm25_repo=_FailingDeleteSaveBM25Repo(),
    )

    with pytest.raises(RuntimeError, match="bm25 save failed during delete"):
        failing_service.delete_document(cleaned_document.document_id)

    assert chroma_repo.count(document_id=cleaned_document.document_id) == before_vector_count
    assert failing_service.bm25_repo.count(document_id=cleaned_document.document_id) == before_bm25_count


@pytest.mark.asyncio
async def test_indexing_service_reindex_failure_keeps_old_indexes(monkeypatch):
    """重建失败时必须保留旧索引，不能先删旧数据再报错。"""
    _use_temp_index_storage(monkeypatch)

    from app.modules.indexing.service import IndexingService

    cleaned_document = _build_cleaned_document(
        document_id="doc-reindex-keep-old",
        index_mode="brute",
        block_token_counts=[800],
    )

    good_service = IndexingService(
        embedding_client=_FakeEmbeddingClient(
            model_name="Qwen/Qwen3-Embedding-8B",
            dimensions=1536,
        )
    )
    first_result = await good_service.index_document(cleaned_document)

    before_vector_count = good_service.chroma_repo.count(document_id=cleaned_document.document_id)
    before_bm25_count = good_service.bm25_repo.count(document_id=cleaned_document.document_id)
    assert before_vector_count == first_result.vector_count
    assert before_bm25_count >= first_result.bm25_count

    bad_service = IndexingService(
        embedding_client=_BadDimensionEmbeddingClient(
            model_name="Qwen/Qwen3-Embedding-8B",
            dimensions=1536,
        )
    )

    with pytest.raises(IndexingError, match="1536"):
        await bad_service.index_document(cleaned_document)

    assert bad_service.chroma_repo.count(document_id=cleaned_document.document_id) == before_vector_count
    assert bad_service.bm25_repo.count(document_id=cleaned_document.document_id) == before_bm25_count


@pytest.mark.asyncio
async def test_embedding_client_request_explicitly_includes_dimensions(monkeypatch):
    """embedding 请求体必须显式携带 dimensions，避免服务端默认值漂移。"""
    import app.clients.embedding_client as embedding_client_module
    from app.clients.embedding_client import EmbeddingClient

    _FakeAsyncClient.captured_json = None
    monkeypatch.setattr(embedding_client_module.httpx, "AsyncClient", _FakeAsyncClient)

    client = EmbeddingClient()

    embeddings = await client.embed(["第一段", "第二段"])

    assert len(embeddings) == 2
    assert _FakeAsyncClient.captured_json is not None
    assert _FakeAsyncClient.captured_json["dimensions"] == 1536


@pytest.mark.asyncio
async def test_indexing_service_keeps_old_indexes_when_bm25_save_fails(monkeypatch):
    """BM25 保存失败时，旧的 Chroma 与 BM25 索引都必须保留。"""
    _use_temp_index_storage(monkeypatch)

    from app.modules.indexing.bm25_repo import BM25Repo
    from app.modules.indexing.chroma_repo import ChromaRepo
    from app.modules.indexing.service import IndexingService

    cleaned_document = _build_cleaned_document(
        document_id="doc-bm25-save-fail-keep-old",
        index_mode="brute",
        block_token_counts=[800],
    )

    chroma_repo = ChromaRepo()
    bm25_repo = BM25Repo()
    service = IndexingService(
        embedding_client=_FakeEmbeddingClient(
            model_name="Qwen/Qwen3-Embedding-8B",
            dimensions=1536,
        ),
        chroma_repo=chroma_repo,
        bm25_repo=bm25_repo,
    )

    first_result = await service.index_document(cleaned_document)
    before_vector_count = chroma_repo.count(document_id=cleaned_document.document_id)
    before_bm25_count = bm25_repo.count(document_id=cleaned_document.document_id)

    assert before_vector_count == first_result.vector_count
    assert before_bm25_count >= first_result.bm25_count

    class _FailingSaveBM25Repo(BM25Repo):
        """故意让 save 失败，用来锁住“替换旧索引时不能丢旧数据”的回归。"""

        def save(self) -> None:
            """模拟 BM25 持久化失败。"""
            raise RuntimeError("bm25 save failed")

    failing_service = IndexingService(
        embedding_client=_FakeEmbeddingClient(
            model_name="Qwen/Qwen3-Embedding-8B",
            dimensions=1536,
        ),
        chroma_repo=chroma_repo,
        bm25_repo=_FailingSaveBM25Repo(),
    )

    with pytest.raises(RuntimeError, match="bm25 save failed"):
        await failing_service.index_document(cleaned_document)

    assert chroma_repo.count(document_id=cleaned_document.document_id) == before_vector_count
    assert failing_service.bm25_repo.count(document_id=cleaned_document.document_id) == before_bm25_count


@pytest.mark.asyncio
async def test_indexing_service_rolls_back_chroma_when_bm25_write_fails(monkeypatch):
    """BM25 写失败后必须回滚刚写入的 Chroma，避免双索引半状态。"""
    _use_temp_index_storage(monkeypatch)

    from app.modules.indexing.chroma_repo import ChromaRepo
    from app.modules.indexing.service import IndexingService

    cleaned_document = _build_cleaned_document(
        document_id="doc-bm25-fail-rollback",
        index_mode="brute",
        block_token_counts=[800],
    )

    chroma_repo = ChromaRepo()
    service = IndexingService(
        embedding_client=_FakeEmbeddingClient(
            model_name="Qwen/Qwen3-Embedding-8B",
            dimensions=1536,
        ),
        chroma_repo=chroma_repo,
        bm25_repo=_BrokenBM25Repo(),
    )

    with pytest.raises(RuntimeError, match="bm25 write failed"):
        await service.index_document(cleaned_document)

    assert chroma_repo.count(document_id=cleaned_document.document_id) == 0



def test_bm25_repo_ignores_legacy_persistence_schema_instead_of_crashing(monkeypatch):
    """BM25Repo 遇到旧持久化格式时，至少要降级为空索引而不是初始化崩掉。"""
    run_dir = _use_temp_index_storage(monkeypatch)
    legacy_index_path = run_dir / "bm25-legacy.pkl"
    legacy_payload = {
        "corpus": ["旧 文档 内容"],
        "tokenized": [["旧", "文档", "内容"]],
        "doc_ids": ["legacy-doc-1"],
    }
    with legacy_index_path.open("wb") as file:
        pickle.dump(legacy_payload, file)

    monkeypatch.setenv("BM25_INDEX_PATH", str(legacy_index_path))
    get_settings.cache_clear()

    from app.modules.indexing.bm25_repo import BM25Repo

    repo = BM25Repo()

    assert repo.count() == 0
    assert repo.query("旧 文档") == []



def test_bm25_repo_downgrades_corrupted_persistence_file_to_empty_index(monkeypatch):
    """BM25Repo 遇到损坏持久化文件时，必须降级为空索引而不是初始化崩溃。"""
    run_dir = _use_temp_index_storage(monkeypatch)
    corrupted_index_path = run_dir / "bm25-corrupted.pkl"
    corrupted_index_path.write_bytes(b"not-a-valid-pickle")

    monkeypatch.setenv("BM25_INDEX_PATH", str(corrupted_index_path))
    get_settings.cache_clear()

    from app.modules.indexing.bm25_repo import BM25Repo

    repo = BM25Repo()

    assert repo.count() == 0
    assert repo.query("任意 查询") == []
