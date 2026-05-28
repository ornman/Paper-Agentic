"""Pipeline 调度模块

类似 Scrapy 的 engine + scheduler 复合体。
负责整个预处理流程的编排。
"""

from .pipeline import (
    PipelineEvent,
    PipelineOrchestrator,
    PipelineStage,
    PipelineState,
)

__all__ = [
    "PipelineOrchestrator",
    "PipelineState",
    "PipelineStage",
    "PipelineEvent",
]
