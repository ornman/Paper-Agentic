from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker


class SQLiteRepo:
    def __init__(self, db_path: str = "./data/app.db"):
        self._engine = create_engine(f"sqlite:///{db_path}")
        self._session_factory = sessionmaker(self._engine)

    def init(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS papers (
                    paper_id    TEXT PRIMARY KEY,
                    title       TEXT NOT NULL DEFAULT '',
                    authors     TEXT NOT NULL DEFAULT '',
                    file_path   TEXT NOT NULL,
                    file_hash   TEXT NOT NULL UNIQUE,
                    file_size   INTEGER,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    total_pages INTEGER,
                    import_time TEXT NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'completed',
                    metadata_json TEXT
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS import_logs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id     TEXT NOT NULL UNIQUE,
                    paper_id    TEXT,
                    file_path   TEXT NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'pending',
                    current_step TEXT,
                    error_msg   TEXT,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS config (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_papers_file_hash ON papers(file_hash)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_import_logs_task_id ON import_logs(task_id)
            """))

    def get_session(self) -> Session:
        return self._session_factory()

    def get_paper_count(self) -> int:
        with self._engine.begin() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM papers WHERE status = 'completed'"))
            return result.scalar() or 0

    def get_chunk_count(self, zvec_stats: dict) -> int:
        return zvec_stats.get("doc_count", 0)
