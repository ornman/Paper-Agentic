from __future__ import annotations

import sqlite3

from app.data_layer.contracts.library_item import LibraryItem


class SQLiteLibraryRepo:
    """SQLite-backed repository for library items."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def init(self) -> None:
        """Create table if it does not exist."""
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

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_items(self) -> list[LibraryItem]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT item_id, title, file_path, file_hash,
                       file_type, import_time, page_count, status
                FROM library_items
                ORDER BY import_time DESC
                """,
            ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def get(self, item_id: str) -> LibraryItem | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT item_id, title, file_path, file_hash,
                       file_type, import_time, page_count, status
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
                       file_type, import_time, page_count, status
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
                     file_type, import_time, page_count, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                    title = excluded.title,
                    file_path = excluded.file_path,
                    file_hash = excluded.file_hash,
                    file_type = excluded.file_type,
                    import_time = excluded.import_time,
                    page_count = excluded.page_count,
                    status = excluded.status
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
        )
