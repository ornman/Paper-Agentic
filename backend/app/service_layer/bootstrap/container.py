"""应用依赖装配"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agent_layer.runtime.chat_model import ChatModel
from app.data_layer.data_persistence.embedding.embedding_client import EmbeddingClient
from app.data_layer.data_persistence.chroma_store.vector_index import VectorIndex
from app.data_layer.data_persistence.chroma_store.keyword_index import KeywordIndex
from app.data_layer.data_persistence.chroma_store.soft_delete import SoftDeleteManager
from app.data_layer.data_persistence.file_management.directory_manager import DirectoryManager
from app.data_layer.data_persistence.document_service import DocumentIngestService
from app.data_layer.data_persistence.sqlite_runtime import (
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
