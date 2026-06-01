"""AppContainer 装配测试

CONT-U01: 所有路由需要的属性都存在
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


class TestContainerAssembly:
    """AppContainer 装配完整性"""

    def test_container_has_all_required_attributes(self, tmp_path):
        """AppContainer 包含 library_routes 和 answer_generator 需要的所有属性"""
        from app.service_layer.config.settings import BackendSettings

        # 构造最小 settings
        settings = BackendSettings(
            chroma_data_dir=str(tmp_path / "chroma"),
            bm25_data_dir=str(tmp_path / "bm25"),
            papers_dir=str(tmp_path / "papers"),
            parsed_dir=str(tmp_path / "parsed"),
            backup_dir=str(tmp_path / "backups"),
            app_db_path=str(tmp_path / "app.db"),
        )

        with patch("app.service_layer.bootstrap.container.ChatModel"):
            from app.service_layer.bootstrap.container import AppContainer
            container = AppContainer(settings)

        # library_routes 需要的属性
        assert hasattr(container, "library_repo")
        assert hasattr(container, "import_task_repo")
        assert hasattr(container, "document_ingest")

        # answer_generator 需要的属性
        assert hasattr(container, "vector_store")
        assert hasattr(container, "keyword_search")
        assert hasattr(container, "chat_model")
        assert hasattr(container, "embedding_client")
        assert hasattr(container, "conversation_repo")
        assert hasattr(container, "conversation_window")
        assert hasattr(container, "editor_context_store")
        assert hasattr(container, "session_persistence")

        # 文件管理
        assert hasattr(container, "soft_delete_manager")
        assert hasattr(container, "directory_manager")

        runner1 = container.turn_runner
        runner2 = container.turn_runner
        assert runner1 is runner2
        assert runner1._window_store is container.conversation_window
        assert runner1._editor_context_store is container.editor_context_store
        assert runner1._persistence is container.session_persistence
        assert runner1._cache_mode == "memory"

        health = container.health()
        assert health["components"]["cache"] == {"status": "ok", "mode": "memory"}

    def test_document_ingest_has_required_dependencies(self, tmp_path):
        """PipelineOrchestrator 装配了所有需要的依赖"""
        from app.service_layer.config.settings import BackendSettings

        settings = BackendSettings(
            chroma_data_dir=str(tmp_path / "chroma"),
            bm25_data_dir=str(tmp_path / "bm25"),
            papers_dir=str(tmp_path / "papers"),
            parsed_dir=str(tmp_path / "parsed"),
            backup_dir=str(tmp_path / "backups"),
            app_db_path=str(tmp_path / "app.db"),
        )

        with patch("app.service_layer.bootstrap.container.ChatModel"):
            from app.service_layer.bootstrap.container import AppContainer
            container = AppContainer(settings)

        di = container.document_ingest
        assert di._vector_index is container.vector_store
        assert di._keyword_index is container.keyword_search
        assert di._soft_delete_manager is container.soft_delete_manager
        assert di._directory_manager is container.directory_manager
        assert di._embedding_client is container.embedding_client
