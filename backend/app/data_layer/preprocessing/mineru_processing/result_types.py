"""MinerU 数据类型定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MinerUTaskState(str, Enum):
    """MinerU 任务状态"""
    PENDING = "pending"
    UPLOADING = "uploading"
    RUNNING = "running"
    CONVERTING = "converting"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class MinerUResult:
    """MinerU 解析结果"""
    markdown: str
    page_count: int
    char_count: int
    success: bool
    error: str | None = None
    task_state: str = ""
    elapsed_s: float = 0.0
    metadata: dict = field(default_factory=dict)
    logs: list[dict] = field(default_factory=list)
    split_count: int = 1


@dataclass
class MinerUProgress:
    """MinerU 进度信息"""
    state: MinerUTaskState
    extracted_pages: int = 0
    total_pages: int = 0
    message: str = ""


ProgressCallback = callable
