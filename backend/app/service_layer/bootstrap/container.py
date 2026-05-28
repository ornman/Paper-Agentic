"""应用依赖装配"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agent_layer.runtime.chat_model import ChatModel
from app.agent_layer.orchestration.tool_loop import ToolRegistry
from app.data_layer.indexing.embedding.embedding_client import EmbeddingClient
from app.data_layer.indexing.chroma_store.vector_index import VectorIndex
from app.data_layer.indexing.chroma_store.keyword_index import KeywordIndex
from app.data_layer.indexing.chroma_store.soft_delete import SoftDeleteManager
from app.data_layer.storage.file_management.directory_manager import DirectoryManager
from app.data_layer.storage.document_service import DocumentIngestService
from app.data_layer.storage.sqlite_runtime import (
    SQLiteConversationRepo,
    SQLiteLibraryRepo,
    SQLiteImportTaskRepo,
)
from app.service_layer.config.settings import BackendSettings


@dataclass
class AppContainer:
    settings: BackendSettings
    redis_client: object | None = field(default=None, init=False)
    conversation_window: object | None = field(default=None, init=False)
    editor_context_store: object | None = field(default=None, init=False)
    redis_health: dict = field(default_factory=lambda: {"status": "unavailable", "detail": "not initialized"}, init=False)

    def __post_init__(self) -> None:
        self.settings.ensure_runtime_dirs()

        # ── 基础设施 ──
        self.vector_store = VectorIndex(str(self.settings.chroma_data_dir))
        self.keyword_search = KeywordIndex(str(self.settings.bm25_data_dir))
        self.chat_model = ChatModel(self.settings)
        if self.settings.reflection_configured:
            class _ReflectionSettings:
                llm_api_key = self.settings.reflection_api_key
                llm_base_url = self.settings.reflection_base_url
                llm_model = self.settings.reflection_model
                llm_max_tokens = 2048
                llm_temperature = self.settings.reflection_temperature
                llm_timeout = self.settings.reflection_timeout
                llm_fallback_models = ""
                chunk_max_context = 8000

            self.reflection_chat_model: ChatModel | None = ChatModel(_ReflectionSettings())
        else:
            self.reflection_chat_model = None
        self.embedding_client = EmbeddingClient(
            api_key=self.settings.embedding_api_key,
            base_url=self.settings.embedding_base_url,
            model=self.settings.embedding_model,
            dimensions=self.settings.embedding_dimensions,
            timeout=self.settings.embedding_timeout,
            batch_size=self.settings.embedding_batch_size,
            max_concurrency=self.settings.embedding_max_concurrency,
        )

        # ── 文件与删除管理 ──
        self.soft_delete_manager = SoftDeleteManager(
            index_dir=str(self.settings.chroma_data_dir),
            retention_days=7,
        )
        self.directory_manager = DirectoryManager(
            papers_dir=str(self.settings.papers_dir),
            parsed_dir=str(self.settings.parsed_dir),
            backups_dir=str(self.settings.backup_dir),
        )

        # ── 文档导入服务 ──
        self.document_ingest = DocumentIngestService(
            config=self.settings,
            vector_index=self.vector_store,
            keyword_index=self.keyword_search,
            soft_delete_manager=self.soft_delete_manager,
            directory_manager=self.directory_manager,
            embedding_client=self.embedding_client,
        )

        # ── SQLite 业务 Repo ──
        db_path = str(self.settings.app_db_path)
        self.conversation_repo = SQLiteConversationRepo(db_path)
        self.library_repo = SQLiteLibraryRepo(db_path)
        self.import_task_repo = SQLiteImportTaskRepo(db_path)

        # ── 导入进度总线 ──
        from app.service_layer.sse.import_progress_bus import ImportProgressBus
        self.import_progress_bus = ImportProgressBus()

    @property
    def turn_runner(self) -> "TurnRunner":
        """构建 TurnRunner 实例（含 ToolRegistry）"""
        from app.agent_layer.orchestration.turn_runner import TurnRunner
        from app.agent_layer.planning.retrieval_gate import should_retrieve
        from app.agent_layer.planning.snapshot_builder import build_snapshot
        from app.agent_layer.response.block_streamer import stream_to_blocks
        from app.agent_layer.response.source_mapper import map_sources
        from app.agent_layer.session.editor_context_store import EditorContextStore
        from app.agent_layer.session.persistence import SessionPersistence
        from app.agent_layer.session.window_store import ConversationWindowStore

        window_store = self.conversation_window or ConversationWindowStore.from_context_window(
            context_window_tokens=self.settings.context_window_tokens,
            max_output_tokens=self.settings.max_output_tokens,
        )
        editor_store = self.editor_context_store or EditorContextStore()
        persistence = SessionPersistence()

        cache_mode = "unavailable"
        if self.redis_health.get("status") == "ok":
            cache_mode = "connected"
        elif self.conversation_window is not None:
            cache_mode = "degraded"

        tool_registry = _build_tool_registry(
            chat_model=self.chat_model,
            vector_store=self.vector_store,
            keyword_search=self.keyword_search,
            embedding_client=self.embedding_client,
        )

        return TurnRunner(
            chat_model=self.chat_model,
            snapshot_builder=build_snapshot,
            retrieval_gate=should_retrieve,
            source_mapper=map_sources,
            block_streamer=stream_to_blocks,
            window_store=window_store,
            editor_context_store=editor_store,
            persistence=persistence,
            vector_store=self.vector_store,
            keyword_search=self.keyword_search,
            embedding_client=self.embedding_client,
            tool_registry=tool_registry,
            cache_mode=cache_mode,
            reflection_model=self.reflection_chat_model,
        )

    async def initialize(self) -> None:
        self.vector_store.init()
        self.keyword_search.init()
        self.soft_delete_manager.init()
        self.directory_manager.init()
        self.conversation_repo.init()
        self.library_repo.init()
        self.import_task_repo.init()

    async def close(self) -> None:
        await self.chat_model.close()
        await self.embedding_client.close()
        self.vector_store.close()

    def health(self) -> dict:
        components = {
            "chroma": {"status": "ok", **self.vector_store.stats},
            "bm25": {"status": "ok", "doc_count": self.keyword_search.doc_count},
            "redis": self.redis_health,
            "llm_config": {"status": "ok" if self.settings.llm_configured else "unavailable"},
            "embedding_config": {"status": "ok" if self.settings.embedding_configured else "unavailable"},
        }
        statuses = {name: value.get("status") for name, value in components.items()}
        if any(status == "error" for status in statuses.values()):
            overall = "error"
        elif any(status != "ok" for status in statuses.values()):
            overall = "degraded"
        else:
            overall = "ok"
        return {"status": overall, "components": components}


def _build_tool_registry(
    chat_model: ChatModel,
    vector_store: VectorIndex,
    keyword_search: KeywordIndex,
    embedding_client: EmbeddingClient,
) -> ToolRegistry:
    """注册三个内部工具：retrieve、read_anchor、compact_history"""
    from app.data_layer.retrieval.fusion.rrf_fusion import rrf_fuse
    from app.agent_layer.hooks.compact import compact_conversation

    registry = ToolRegistry()

    async def _retrieve(args: dict) -> dict:
        query = args.get("query", "")
        paper_ids = args.get("paper_ids")
        dense_results = []
        sparse_results = []
        try:
            qv = await embedding_client.embed_single(query)
            dense_results = vector_store.query(qv, topk=20, paper_ids=paper_ids)
        except Exception:
            pass
        try:
            sparse_results = keyword_search.query(query, topk=20, paper_ids=paper_ids)
        except Exception:
            pass
        fused = rrf_fuse(dense_results, sparse_results, topk=10, keyword_index=keyword_search)
        return [{"id": d.id, "content": d.content, "metadata": d.metadata} for d in fused]

    async def _read_anchor(args: dict) -> dict:
        anchor_id = args.get("anchor_id", "")
        paper_id = args.get("paper_id", "")
        if not anchor_id and not paper_id:
            return {"error": "需要 anchor_id 或 paper_id"}
        # 从向量库中按 metadata 过滤
        results = vector_store.query([0.0] * 1536, topk=1, paper_ids=[paper_id] if paper_id else None)
        if results:
            return {"content": results[0].fields.get("content", ""), "metadata": results[0].fields}
        return {"error": "未找到"}

    async def _compact_history(args: dict) -> dict:
        messages = args.get("messages", [])
        summary = await compact_conversation(chat_model, messages)
        return {"summary": summary}

    registry.register("retrieve", _retrieve)
    registry.register("read_anchor", _read_anchor)
    registry.register("compact_history", _compact_history)
    return registry
