"""SQLiteLibraryRepo 筛选 + 迁移测试"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.data_layer.storage.sqlite_runtime._types import LibraryItem
from app.data_layer.storage.sqlite_runtime.library_repo import SQLiteLibraryRepo


@pytest.fixture
def repo(tmp_path: Path) -> SQLiteLibraryRepo:
    db_path = str(tmp_path / "test.db")
    r = SQLiteLibraryRepo(db_path)
    r.init()
    return r


def _insert(repo: SQLiteLibraryRepo, **overrides) -> LibraryItem:
    defaults = dict(
        item_id="p1", title="Test", file_path="/tmp/test.pdf",
        file_hash="h1", file_type=".pdf", import_time="2025-01-01",
        page_count=10, status="ready", authors="", year=None,
    )
    defaults.update(overrides)
    item = LibraryItem(**defaults)
    repo.upsert(item)
    return item


class TestMigration:
    def test_init_adds_authors_and_year_columns(self, repo: SQLiteLibraryRepo):
        with sqlite3.connect(repo._db_path) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(library_items)").fetchall()}
        assert "authors" in cols
        assert "year" in cols

    def test_migration_is_idempotent(self, repo: SQLiteLibraryRepo):
        repo.init()
        repo.init()
        with sqlite3.connect(repo._db_path) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(library_items)").fetchall()}
        assert "authors" in cols
        assert "year" in cols

    def test_old_data_survives_migration(self, repo: SQLiteLibraryRepo):
        _insert(repo, item_id="old1", title="Old Paper")
        items = repo.list_items()
        assert len(items) == 1
        assert items[0].authors == ""
        assert items[0].year is None


class TestUpsertWithNewFields:
    def test_upsert_with_authors_and_year(self, repo: SQLiteLibraryRepo):
        _insert(repo, item_id="p1", title="Paper", authors="Alice", year=2024)
        item = repo.get("p1")
        assert item.authors == "Alice"
        assert item.year == 2024

    def test_upsert_overwrites_authors_and_year(self, repo: SQLiteLibraryRepo):
        _insert(repo, item_id="p1", authors="Old", year=2020)
        _insert(repo, item_id="p1", authors="New", year=2024)
        item = repo.get("p1")
        assert item.authors == "New"
        assert item.year == 2024


class TestListItemsFiltered:
    def test_filter_by_title(self, repo: SQLiteLibraryRepo):
        _insert(repo, item_id="p1", title="RAG Survey")
        _insert(repo, item_id="p2", title="LLM Review")
        result = repo.list_items_filtered(title="RAG")
        assert len(result) == 1
        assert result[0].title == "RAG Survey"

    def test_filter_by_title_partial(self, repo: SQLiteLibraryRepo):
        _insert(repo, item_id="p1", title="A Survey on RAG")
        _insert(repo, item_id="p2", title="LLM Review")
        result = repo.list_items_filtered(title="Survey")
        assert len(result) == 1

    def test_filter_by_authors_exact(self, repo: SQLiteLibraryRepo):
        _insert(repo, item_id="p1", authors="Alice")
        _insert(repo, item_id="p2", authors="Bob")
        _insert(repo, item_id="p3", authors="Alice and Bob")
        result = repo.list_items_filtered(authors="Alice")
        assert len(result) == 1
        assert result[0].authors == "Alice"

    def test_filter_by_authors_case_insensitive(self, repo: SQLiteLibraryRepo):
        _insert(repo, item_id="p1", authors="Alice")
        result = repo.list_items_filtered(authors="alice")
        assert len(result) == 1

    def test_filter_by_year_range(self, repo: SQLiteLibraryRepo):
        _insert(repo, item_id="p1", year=2020)
        _insert(repo, item_id="p2", year=2023)
        _insert(repo, item_id="p3", year=2025)
        result = repo.list_items_filtered(year_from=2022, year_to=2024)
        assert len(result) == 1
        assert result[0].year == 2023

    def test_filter_excludes_null_year(self, repo: SQLiteLibraryRepo):
        _insert(repo, item_id="p1", year=None)
        _insert(repo, item_id="p2", year=2023)
        result = repo.list_items_filtered(year_from=2020)
        assert len(result) == 1
        assert result[0].year == 2023

    def test_filter_combined(self, repo: SQLiteLibraryRepo):
        _insert(repo, item_id="p1", title="RAG", authors="Alice", year=2023)
        _insert(repo, item_id="p2", title="RAG", authors="Bob", year=2023)
        _insert(repo, item_id="p3", title="RAG", authors="Alice", year=2025)
        result = repo.list_items_filtered(title="RAG", authors="Alice", year_from=2022, year_to=2024)
        assert len(result) == 1
        assert result[0].item_id == "p1"

    def test_no_filters_returns_all(self, repo: SQLiteLibraryRepo):
        _insert(repo, item_id="p1")
        _insert(repo, item_id="p2")
        result = repo.list_items_filtered()
        assert len(result) == 2
