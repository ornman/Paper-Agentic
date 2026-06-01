"""papers_routes 单元测试"""

from __future__ import annotations

import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(item_id="p1", title="Test Paper", file_path="/tmp/test.pdf",
               file_hash="abc123", page_count=10, status="ready",
               authors="", year=None):
    return types.SimpleNamespace(
        item_id=item_id, title=title, file_path=file_path,
        file_hash=file_hash, file_type=".pdf", import_time="2025-01-01",
        page_count=page_count, status=status, authors=authors, year=year,
    )


def _build_app(items=None, *, paper_dir_exists=False, paper_file_exists=True, filtered_items=None):
    """构造带 mock container 的 FastAPI app"""
    from app.service_layer.api.papers_routes import router

    app = FastAPI()
    app.include_router(router)

    container = MagicMock()
    container.library_repo.list_items.return_value = items or []
    container.library_repo.list_items_filtered.return_value = filtered_items or items or []
    container.library_repo.get.return_value = (items[0] if items else None)

    # directory_manager mock
    mock_papers_dir = MagicMock()
    if paper_dir_exists:
        paper_dir = MagicMock()
        paper_dir.exists.return_value = True
        if paper_file_exists:
            pdf_file = MagicMock()
            pdf_file.is_file.return_value = True
            pdf_file.suffix.lower.return_value = ".pdf"
            pdf_file.__str__ = lambda self: "/tmp/test.pdf"
            paper_dir.iterdir.return_value = [pdf_file]
        else:
            paper_dir.iterdir.return_value = []
        mock_papers_dir.__truediv__ = lambda self, x: paper_dir
    else:
        missing_dir = MagicMock()
        missing_dir.exists.return_value = False
        mock_papers_dir.__truediv__ = lambda self, x: missing_dir

    container.directory_manager._papers_dir = mock_papers_dir

    app.state.container = container
    return app, container


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListPapers:
    def test_empty_list(self):
        app, _ = _build_app(items=[])
        client = TestClient(app)
        resp = client.get("/papers")
        assert resp.status_code == 200
        data = resp.json()
        assert "papers" in data
        assert data["papers"] == []

    def test_returns_mapped_fields(self):
        item = _make_item()
        app, _ = _build_app(items=[item])
        client = TestClient(app)
        resp = client.get("/papers")
        assert resp.status_code == 200
        papers = resp.json()["papers"]
        assert len(papers) == 1
        p = papers[0]
        assert p["paper_id"] == "p1"
        assert p["title"] == "Test Paper"
        assert p["total_pages"] == 10
        assert p["status"] == "ready"

    def test_multiple_items(self):
        items = [_make_item(item_id=f"p{i}", title=f"Paper {i}") for i in range(3)]
        app, _ = _build_app(items=items)
        client = TestClient(app)
        resp = client.get("/papers")
        assert len(resp.json()["papers"]) == 3


class TestOpenPaper:
    def test_item_not_found(self):
        app, container = _build_app(items=[])
        container.library_repo.get.return_value = None
        client = TestClient(app)
        resp = client.get("/papers/nonexistent/open")
        assert resp.status_code == 404

    def test_paper_dir_not_found(self):
        app, _ = _build_app(items=[_make_item()], paper_dir_exists=False)
        client = TestClient(app)
        resp = client.get("/papers/p1/open")
        assert resp.status_code == 404

    def test_no_file_in_dir(self):
        app, _ = _build_app(items=[_make_item()], paper_dir_exists=True, paper_file_exists=False)
        client = TestClient(app)
        resp = client.get("/papers/p1/open")
        assert resp.status_code == 404


class TestDeletePaper:
    def test_item_not_found(self):
        app, container = _build_app(items=[])
        container.library_repo.get.return_value = None
        client = TestClient(app)
        resp = client.delete("/papers/nonexistent")
        assert resp.status_code == 404

    def test_delete_success(self):
        item = _make_item()
        app, container = _build_app(items=[item])
        client = TestClient(app)
        resp = client.delete("/papers/p1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        container.document_ingest.delete_document.assert_called_once_with("p1")


class TestPaperFields:
    def test_returns_year_field(self):
        item = _make_item(year=2024)
        app, _ = _build_app(items=[item])
        client = TestClient(app)
        resp = client.get("/papers")
        assert resp.json()["papers"][0]["year"] == 2024

    def test_year_null_when_missing(self):
        item = _make_item(year=None)
        app, _ = _build_app(items=[item])
        client = TestClient(app)
        resp = client.get("/papers")
        assert resp.json()["papers"][0]["year"] is None

    def test_returns_authors_field(self):
        item = _make_item(authors="Alice, Bob")
        app, _ = _build_app(items=[item])
        client = TestClient(app)
        resp = client.get("/papers")
        assert resp.json()["papers"][0]["authors"] == "Alice, Bob"


class TestPaperFiltering:
    def test_filter_by_title(self):
        items = [_make_item(item_id="p1", title="RAG Survey"), _make_item(item_id="p2", title="LLM Review")]
        filtered = [items[0]]
        app, container = _build_app(items=items, filtered_items=filtered)
        client = TestClient(app)
        resp = client.get("/papers?title=RAG")
        assert resp.status_code == 200
        assert len(resp.json()["papers"]) == 1
        container.library_repo.list_items_filtered.assert_called_once_with(
            title="RAG", authors=None, year_from=None, year_to=None,
        )

    def test_filter_by_authors(self):
        items = [_make_item(item_id="p1", authors="Alice")]
        app, container = _build_app(items=items, filtered_items=items)
        client = TestClient(app)
        resp = client.get("/papers?authors=Alice")
        assert resp.status_code == 200
        container.library_repo.list_items_filtered.assert_called_once_with(
            title=None, authors="Alice", year_from=None, year_to=None,
        )

    def test_filter_by_year_range(self):
        items = [_make_item(item_id="p1", year=2023)]
        app, container = _build_app(items=items, filtered_items=items)
        client = TestClient(app)
        resp = client.get("/papers?year_from=2020&year_to=2025")
        assert resp.status_code == 200
        container.library_repo.list_items_filtered.assert_called_once_with(
            title=None, authors=None, year_from=2020, year_to=2025,
        )

    def test_no_filter_uses_list_items(self):
        items = [_make_item()]
        app, container = _build_app(items=items)
        client = TestClient(app)
        resp = client.get("/papers")
        assert resp.status_code == 200
        container.library_repo.list_items.assert_called_once()
        container.library_repo.list_items_filtered.assert_not_called()
