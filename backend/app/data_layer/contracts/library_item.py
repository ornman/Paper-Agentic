from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


@dataclass
class ImportTask:
    task_id: str
    file_path: str
    status: str = "queued"
    message: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    paper_id: str = ""
    completed_at: str = ""
