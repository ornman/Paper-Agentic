from __future__ import annotations

import sqlite3

from ._types import LibraryItem, utc_now_iso


class SQLiteLibraryRepo:
    """SQLite-backed repository for library items."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def init(self) -> None:
        """Create table if it does not exist, then migrate missing columns."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS library_items (
                    item_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    file_path TEXT NOT NULL DEFAULT '',
                    file_hash TEXT NOT NULL DEFAULT '',
                    file_type TEXT NOT NULL DEFAULT '',
                    import_time TEXT NOT NULL DEFAULT '',
                    page_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'ready'
                )
                """
            )
            conn.commit()
            # 向后兼容迁移：添加 authors、year、file_size 列
            existing = {row[1] for row in conn.execute("PRAGMA table_info(library_items)").fetchall()}
            if "authors" not in existing:
                conn.execute("ALTER TABLE library_items ADD COLUMN authors TEXT DEFAULT ''")
            if "year" not in existing:
                conn.execute("ALTER TABLE library_items ADD COLUMN year INTEGER")
            if "file_size" not in existing:
                conn.execute("ALTER TABLE library_items ADD COLUMN file_size INTEGER DEFAULT 0")
            if "deleted_at" not in existing:
                conn.execute("ALTER TABLE library_items ADD COLUMN deleted_at TEXT DEFAULT NULL")
            conn.commit()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_items(self) -> list[LibraryItem]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT item_id, title, file_path, file_hash,
                       file_type, import_time, page_count, status,
                       authors, year, file_size, deleted_at
                FROM library_items
                WHERE deleted_at IS NULL
                ORDER BY import_time DESC
                """,
            ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def list_items_filtered(
        self,
        *,
        title: str | None = None,
        authors: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[LibraryItem]:
        """带筛选条件的查询"""
        clauses: list[str] = []
        params: list = []
        if title:
            clauses.append("title LIKE ?")
            params.append(f"%{title}%")
        if authors:
            clauses.append("LOWER(TRIM(authors)) = LOWER(TRIM(?))")
            params.append(authors)
        if year_from is not None:
            clauses.append("(year IS NOT NULL AND year >= ?)")
            params.append(year_from)
        if year_to is not None:
            clauses.append("(year IS NOT NULL AND year <= ?)")
            params.append(year_to)

        base_where = "deleted_at IS NULL"
        if clauses:
            full_where = f"WHERE {base_where} AND {' AND '.join(clauses)}"
        else:
            full_where = f"WHERE {base_where}"
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT item_id, title, file_path, file_hash,
                       file_type, import_time, page_count, status,
                       authors, year, file_size, deleted_at
                FROM library_items
                {full_where}
                ORDER BY import_time DESC
                """,
                params,
            ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def get(self, item_id: str) -> LibraryItem | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT item_id, title, file_path, file_hash,
                       file_type, import_time, page_count, status,
                       authors, year, file_size, deleted_at
                FROM library_items
                WHERE item_id = ?
                """,
                (item_id,),
            ).fetchone()
        return self._row_to_item(row) if row else None

    def get_by_id(self, item_id: str) -> LibraryItem | None:
        """Alias for :meth:`get`."""
        return self.get(item_id)

    def get_by_hash(self, file_hash: str) -> LibraryItem | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT item_id, title, file_path, file_hash,
                       file_type, import_time, page_count, status,
                       authors, year, file_size, deleted_at
                FROM library_items
                WHERE file_hash = ?
                """,
                (file_hash,),
            ).fetchone()
        return self._row_to_item(row) if row else None

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def upsert(self, item: LibraryItem) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO library_items
                    (item_id, title, file_path, file_hash,
                     file_type, import_time, page_count, status,
                     authors, year, file_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                    title = excluded.title,
                    file_path = excluded.file_path,
                    file_hash = excluded.file_hash,
                    file_type = excluded.file_type,
                    import_time = excluded.import_time,
                    page_count = excluded.page_count,
                    status = excluded.status,
                    authors = excluded.authors,
                    year = excluded.year,
                    file_size = excluded.file_size
                """,
                (
                    item.item_id,
                    item.title,
                    item.file_path,
                    item.file_hash,
                    item.file_type,
                    item.import_time,
                    item.page_count,
                    item.status,
                    item.authors,
                    item.year,
                    item.file_size,
                ),
            )
            conn.commit()

    def delete(self, item_id: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "DELETE FROM library_items WHERE item_id = ?",
                (item_id,),
            )
            conn.commit()

    def soft_delete(self, item_id: str) -> None:
        now = utc_now_iso()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE library_items SET deleted_at = ? WHERE item_id = ?",
                (now, item_id),
            )
            conn.commit()

    def list_trashed(self) -> list[LibraryItem]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT item_id, title, file_path, file_hash,
                       file_type, import_time, page_count, status,
                       authors, year, file_size, deleted_at
                FROM library_items
                WHERE deleted_at IS NOT NULL
                ORDER BY deleted_at DESC
                """,
            ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def restore(self, item_id: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE library_items SET deleted_at = NULL WHERE item_id = ?",
                (item_id,),
            )
            conn.commit()

    def hard_delete(self, item_id: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "DELETE FROM library_items WHERE item_id = ?",
                (item_id,),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_item(row: tuple) -> LibraryItem:
        return LibraryItem(
            item_id=row[0],
            title=row[1],
            file_path=row[2],
            file_hash=row[3],
            file_type=row[4],
            import_time=row[5],
            page_count=row[6],
            status=row[7],
            authors=row[8] if len(row) > 8 else "",
            year=row[9] if len(row) > 9 and row[9] is not None else "",
            file_size=row[10] if len(row) > 10 else 0,
            deleted_at=row[11] if len(row) > 11 else None,
        )
