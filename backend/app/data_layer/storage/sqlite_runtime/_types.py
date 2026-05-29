"""sqlite_runtime 内部类型定义

不对外暴露。service_layer / agent_layer 应定义自己的 DTO，
不直接依赖此模块。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── 文档库 ──────────────────────────────────────────────────


@dataclass
class LibraryItem:
    item_id: str
    title: str
    file_path: str
    file_hash: str = ""
    file_type: str = ""
    import_time: str = ""
    page_count: int = 0
    status: str = "ready"
    authors: str = ""
    year: int | None = None


@dataclass
class ImportTask:
    task_id: str
    file_path: str
    status: str = "queued"
    message: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    paper_id: str = ""
    completed_at: str = ""


# ── 对话 ────────────────────────────────────────────────────


@dataclass
class ConversationSession:
    session_id: str
    title: str
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ConversationMessage:
    session_id: str
    role: str
    content: str
    created_at: str = ""
    sources_json: str | None = None
