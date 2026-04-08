# 文档状态机与 library 模块的最小集成测试
# 这里只覆盖 Task 3 要求的最小行为：
# 1. 文档状态能按 pending -> parsing -> cleaning -> indexing -> completed 推进
# 2. 文档库记录能通过 service + repository 持久化到 SQLite
# 3. API 总路由已挂载 Task 3 需要的 library 端点

import uuid
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.repositories import sqlite_repo


def _use_temp_sqlite_database(monkeypatch) -> Path:
    """切换到项目内临时 SQLite，避免 pytest 在 Windows 同步盘上清理临时目录时报错。

    这里还会把当前工作目录切到一个不含 .env 的临时目录，
    防止 backend 根目录下的 .env 把与 Task 3 无关的旧字段注入 Settings，
    从而让测试失败原因偏离当前任务。
    """
    backend_root = Path(__file__).resolve().parents[2]
    temp_dir = backend_root / "data" / "test-temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(temp_dir)
    db_path = temp_dir / f"library-task3-{uuid.uuid4()}.db"
    monkeypatch.setenv("SQLITE_DB_PATH", str(db_path))
    get_settings.cache_clear()
    sqlite_repo._engine = None
    return db_path


def test_document_status_can_progress_to_completed():
    """文档状态机至少要支持计划里要求的主链路推进。"""
    from app.modules.library.models import DocumentRecord

    record = DocumentRecord(status="pending")
    record = record.transition("parsing")
    record = record.transition("cleaning")
    record = record.transition("indexing")
    record = record.transition("completed")

    assert record.status == "completed"


def test_library_service_can_persist_document_record(monkeypatch):
    """导入后的文档记录必须能落到 SQLite，并能再次读出。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.library.service import LibraryService

    service = LibraryService()
    created = service.import_document(
        file_path="D:/papers/test-paper.pdf",
        title="测试论文",
        index_mode="brute",
        tags=["测试", "论文"],
    )

    documents = service.list_documents()

    assert created.document_id
    assert len(documents) == 1
    assert documents[0].title == "测试论文"
    assert documents[0].file_path == "D:/papers/test-paper.pdf"
    assert documents[0].index_mode == "brute"
    assert documents[0].status == "pending"
    assert documents[0].tags == ["测试", "论文"]


def test_library_routes_are_registered():
    """Task 3 要求的 library 路由必须挂到 API v1 总路由上。"""
    from app.api.v1.router import api_router

    registered_routes = {
        (method, route.path)
        for route in api_router.routes
        for method in route.methods
        if method in {"GET", "POST", "DELETE"}
    }

    expected_routes = {
        ("POST", "/api/v1/library/import"),
        ("GET", "/api/v1/library/documents"),
        ("DELETE", "/api/v1/library/documents/{document_id}"),
        ("POST", "/api/v1/library/documents/{document_id}/reindex"),
    }

    assert expected_routes.issubset(registered_routes)


def test_import_document_rejects_blank_file_path(monkeypatch):
    """空白 file_path 必须在服务层边界被拒绝，不能落库。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.library.service import LibraryService

    service = LibraryService()

    with pytest.raises(ValueError, match="file_path"):
        service.import_document(file_path="   ", title="无效路径")

    assert service.list_documents() == []


def test_import_document_rejects_invalid_index_mode(monkeypatch):
    """非法 index_mode 必须在 Task 3 范围内被拒绝，不能落库。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.library.service import LibraryService

    service = LibraryService()

    with pytest.raises(ValueError, match="index_mode"):
        service.import_document(
            file_path="D:/papers/test-paper.pdf",
            title="非法索引模式",
            index_mode="invalid_mode",
        )

    assert service.list_documents() == []


def test_reindex_completed_document_does_not_enter_indexing_stuck_state(monkeypatch):
    """没有真实索引流程前，completed 文档重建索引不能写成卡死的 indexing。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.library.service import LibraryService

    service = LibraryService()
    created = service.import_document(
        file_path="D:/papers/completed-paper.pdf",
        title="已完成文档",
        index_mode="brute",
    )
    completed = service.transition_document(created.document_id, "parsing")
    completed = service.transition_document(completed.document_id, "cleaning")
    completed = service.transition_document(completed.document_id, "indexing")
    completed = service.transition_document(completed.document_id, "completed")

    with pytest.raises(ValueError, match="completed"):
        service.reindex_document(completed.document_id)

    reloaded = service.get_document(completed.document_id)
    assert reloaded.status == "completed"
    assert reloaded.index_mode == "brute"
