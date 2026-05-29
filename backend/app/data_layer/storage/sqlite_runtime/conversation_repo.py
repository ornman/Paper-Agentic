from __future__ import annotations

import sqlite3

from ._types import ConversationMessage, ConversationSession


class SQLiteConversationRepo:
    """SQLite-backed repository for conversation sessions and messages."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def init(self) -> None:
        """Create tables if they do not exist."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT '',
                    sources_json TEXT,
                    FOREIGN KEY (session_id) REFERENCES conversation_sessions(session_id)
                )
                """
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ConversationSession]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT session_id, title, created_at, updated_at
                FROM conversation_sessions
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [
            ConversationSession(
                session_id=r[0],
                title=r[1],
                created_at=r[2],
                updated_at=r[3],
            )
            for r in rows
        ]

    def upsert_session(self, session: ConversationSession) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO conversation_sessions (session_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    title = excluded.title,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    session.session_id,
                    session.title,
                    session.created_at,
                    session.updated_at,
                ),
            )
            conn.commit()

    def get_session(self, session_id: str) -> ConversationSession | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT session_id, title, created_at, updated_at
                FROM conversation_sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return ConversationSession(
            session_id=row[0],
            title=row[1],
            created_at=row[2],
            updated_at=row[3],
        )

    def delete_session(self, session_id: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "DELETE FROM conversation_messages WHERE session_id = ?",
                (session_id,),
            )
            conn.execute(
                "DELETE FROM conversation_sessions WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()

    def rename_session(self, session_id: str, title: str) -> bool:
        """重命名会话，返回是否成功"""
        from ._types import utc_now_iso
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE conversation_sessions
                SET title = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (title, utc_now_iso(), session_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def search_sessions(self, keyword: str, limit: int = 20) -> list[ConversationSession]:
        """按标题搜索会话"""
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT session_id, title, created_at, updated_at
                FROM conversation_sessions
                WHERE title LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (f"%{keyword}%", limit),
            ).fetchall()
        return [
            ConversationSession(
                session_id=r[0],
                title=r[1],
                created_at=r[2],
                updated_at=r[3],
            )
            for r in rows
        ]

    def search_messages(self, keyword: str, session_id: str | None = None, limit: int = 20) -> list[ConversationMessage]:
        """按内容搜索消息，可选限定会话"""
        with sqlite3.connect(self._db_path) as conn:
            if session_id:
                rows = conn.execute(
                    """
                    SELECT session_id, role, content, created_at, sources_json
                    FROM conversation_messages
                    WHERE content LIKE ? AND session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (f"%{keyword}%", session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT session_id, role, content, created_at, sources_json
                    FROM conversation_messages
                    WHERE content LIKE ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (f"%{keyword}%", limit),
                ).fetchall()
        return [
            ConversationMessage(
                session_id=r[0],
                role=r[1],
                content=r[2],
                created_at=r[3],
                sources_json=r[4],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def get_messages(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[ConversationMessage]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT session_id, role, content, created_at, sources_json
                FROM conversation_messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        # Return in chronological order (oldest first)
        return [
            ConversationMessage(
                session_id=r[0],
                role=r[1],
                content=r[2],
                created_at=r[3],
                sources_json=r[4],
            )
            for r in reversed(rows)
        ]

    def save_message(self, msg: ConversationMessage) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO conversation_messages
                    (session_id, role, content, created_at, sources_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    msg.session_id,
                    msg.role,
                    msg.content,
                    msg.created_at,
                    msg.sources_json,
                ),
            )
            conn.commit()
