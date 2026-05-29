from __future__ import annotations

import sqlite3

from ._types import ImportTask


class SQLiteImportTaskRepo:
    """SQLite-backed repository for PDF import tasks."""

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
                CREATE TABLE IF NOT EXISTS import_tasks (
                    task_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL DEFAULT '',
                    paper_id TEXT DEFAULT '',
                    status TEXT DEFAULT 'queued',
                    message TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    completed_at TEXT DEFAULT ''
                )
                """
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, task_id: str) -> ImportTask | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT task_id, file_path, paper_id, status,
                       message, created_at, completed_at
                FROM import_tasks
                WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()
        return self._row_to_task(row) if row else None

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def create(self, task: ImportTask) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO import_tasks
                    (task_id, file_path, paper_id, status,
                     message, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.file_path,
                    task.paper_id,
                    task.status,
                    task.message,
                    task.created_at,
                    task.completed_at,
                ),
            )
            conn.commit()

    def update_status(
        self,
        task_id: str,
        status: str,
        message: str = "",
        paper_id: str = "",
    ) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                UPDATE import_tasks
                SET status = ?,
                    message = ?,
                    paper_id = CASE WHEN ? != '' THEN ? ELSE paper_id END,
                    completed_at = CASE WHEN ? IN ('done', 'failed', 'error') THEN datetime('now') ELSE completed_at END
                WHERE task_id = ?
                """,
                (
                    status,
                    message,
                    paper_id,
                    paper_id,
                    status,
                    task_id,
                ),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_task(row: tuple) -> ImportTask:
        return ImportTask(
            task_id=row[0],
            file_path=row[1],
            paper_id=row[2] or "",
            status=row[3],
            message=row[4] or "",
            created_at=row[5],
            completed_at=row[6] or "",
        )
