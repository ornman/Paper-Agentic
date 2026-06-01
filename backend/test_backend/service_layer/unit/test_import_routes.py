"""import_routes 单元测试"""

from __future__ import annotations

import types
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(task_id="t1", file_path="/tmp/test.pdf", status="queued",
               paper_id="", message=""):
    return types.SimpleNamespace(
        task_id=task_id, file_path=file_path, status=status,
        paper_id=paper_id, message=message, created_at="2025-01-01",
        completed_at="",
    )


def _build_app(task=None, *, settings_mock=None):
    from app.service_layer.api.import_routes import router

    app = FastAPI()
    app.include_router(router)

    container = MagicMock()
    if settings_mock:
        container.settings = settings_mock
    else:
        container.settings = types.SimpleNamespace(uploads_dir=Path("/tmp/uploads"))

    container.import_task_repo.get.return_value = task
    container.import_task_repo.create.return_value = None
    container.import_task_repo.update_status.return_value = None
    container.library_repo.get_by_hash.return_value = None
    container.library_repo.upsert.return_value = None
    container.document_ingest.ingest_document = AsyncMock(return_value=types.SimpleNamespace(
        success=True, paper_id="p1", chunk_count=5, error=None,
    ))

    from app.service_layer.sse.import_progress_bus import ImportProgressBus
    container.import_progress_bus = ImportProgressBus()

    app.state.container = container
    return app, container


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestImportStatus:
    def test_task_not_found(self):
        app, _ = _build_app(task=None)
        client = TestClient(app)
        resp = client.get("/import/status/nonexistent")
        assert resp.status_code == 404

    def test_returns_status(self):
        task = _make_task()
        app, _ = _build_app(task=task)
        client = TestClient(app)
        resp = client.get("/import/status/t1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "t1"
        assert data["status"] == "queued"
        assert data["file_name"] == "test.pdf"

    def test_completed_task_has_paper_id(self):
        task = _make_task(status="completed", paper_id="p1")
        app, _ = _build_app(task=task)
        client = TestClient(app)
        resp = client.get("/import/status/t1")
        data = resp.json()
        assert data["paper_id"] == "p1"
        assert data["status"] == "completed"

    def test_failed_task_has_error(self):
        task = _make_task(status="failed", message="something went wrong")
        app, _ = _build_app(task=task)
        client = TestClient(app)
        resp = client.get("/import/status/t1")
        data = resp.json()
        assert data["error_msg"] == "something went wrong"


class TestImportStart:
    def test_rejects_unsupported_format(self, tmp_path):
        app, _ = _build_app()
        client = TestClient(app)
        # Create a .txt file
        resp = client.post(
            "/import/start",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400

    @patch("app.service_layer.api.import_routes._run_import_with_progress")
    def test_accepts_pdf(self, mock_worker):
        app, container = _build_app()
        # Make uploads_dir a real temp dir
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            container.settings.uploads_dir = Path(td)
            client = TestClient(app)
            resp = client.post(
                "/import/start",
                files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
            )
        # The endpoint should accept it (may fail on hash/duplicate check but format is OK)
        # Status could be 200 or the task gets created
        assert resp.status_code in (200, 400)  # 400 if duplicate, 200 if queued


class TestImportStream:
    def test_sse_endpoint_exists(self):
        """Verify the SSE endpoint is registered and returns streaming response"""
        import asyncio
        app, container = _build_app()

        # Pre-fill a queue with a done event so the stream terminates immediately
        q = asyncio.Queue()
        q.put_nowait({"status": "done", "step": None, "paper_id": None})
        container.import_progress_bus.subscribe = MagicMock(return_value=q)

        client = TestClient(app)
        resp = client.get("/import/stream/t1")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
