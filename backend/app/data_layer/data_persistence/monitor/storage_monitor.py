"""持久化层监控器

监控持久化层的运行状态、延迟、存储健康。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("paper-assistant")


@dataclass
class LatencyMetric:
    """延迟指标"""
    operation: str
    duration_ms: int
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    error: str | None = None


@dataclass
class StorageHealth:
    """存储健康状态"""
    chroma_doc_count: int = 0
    bm25_doc_count: int = 0
    papers_size_mb: float = 0.0
    parsed_size_mb: float = 0.0
    last_checked: float = field(default_factory=time.time)


class StorageMonitor:
    """持久化层监控器

    收集和记录持久化层的运行指标。
    """

    def __init__(self, output_dir: str | None = None):
        """
        Args:
            output_dir: 指标输出目录
        """
        self._output_dir = Path(output_dir) if output_dir else None
        self._latency_metrics: list[LatencyMetric] = []
        self._health: StorageHealth = StorageHealth()

    def record_latency(
        self,
        operation: str,
        duration_ms: int,
        success: bool = True,
        error: str = None,
    ):
        """记录延迟指标"""
        metric = LatencyMetric(
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            error=error,
        )
        self._latency_metrics.append(metric)

        # 同时输出到日志
        if success:
            logger.debug("操作 %s 耗时 %dms", operation, duration_ms)
        else:
            logger.warning("操作 %s 失败 %dms: %s", operation, duration_ms, error)

    def update_health(
        self,
        chroma_doc_count: int = None,
        bm25_doc_count: int = None,
        papers_size_mb: float = None,
        parsed_size_mb: float = None,
    ):
        """更新存储健康状态"""
        if chroma_doc_count is not None:
            self._health.chroma_doc_count = chroma_doc_count
        if bm25_doc_count is not None:
            self._health.bm25_doc_count = bm25_doc_count
        if papers_size_mb is not None:
            self._health.papers_size_mb = papers_size_mb
        if parsed_size_mb is not None:
            self._health.parsed_size_mb = parsed_size_mb

        self._health.last_checked = time.time()

    def get_health(self) -> StorageHealth:
        """获取存储健康状态"""
        return self._health

    def get_latency_stats(self, operation: str = None, window_seconds: int = 3600) -> dict:
        """获取延迟统计

        Args:
            operation: 过滤的操作类型
            window_seconds: 时间窗口（秒）

        Returns:
            统计数据
        """
        now = time.time()
        metrics = [
            m for m in self._latency_metrics
            if now - m.timestamp <= window_seconds
            and (operation is None or m.operation == operation)
        ]

        if not metrics:
            return {
                "count": 0,
                "avg_ms": 0,
                "p50_ms": 0,
                "p95_ms": 0,
                "p99_ms": 0,
                "success_rate": 0.0,
            }

        durations = sorted([m.duration_ms for m in metrics])
        success_count = sum(1 for m in metrics if m.success)

        return {
            "count": len(metrics),
            "avg_ms": sum(durations) / len(durations),
            "p50_ms": durations[len(durations) // 2],
            "p95_ms": durations[int(len(durations) * 0.95)],
            "p99_ms": durations[int(len(durations) * 0.99)],
            "success_rate": success_count / len(metrics),
        }

    def save_report(self):
        """保存监控报告"""
        if not self._output_dir:
            return

        self._output_dir.mkdir(parents=True, exist_ok=True)

        report = {
            "timestamp": time.time(),
            "health": {
                "chroma_doc_count": self._health.chroma_doc_count,
                "bm25_doc_count": self._health.bm25_doc_count,
                "papers_size_mb": round(self._health.papers_size_mb, 2),
                "parsed_size_mb": round(self._health.parsed_size_mb, 2),
                "last_checked": self._health.last_checked,
            },
            "latency": {
                "embedding": self.get_latency_stats("embedding"),
                "chroma_write": self.get_latency_stats("chroma_write"),
                "chroma_query": self.get_latency_stats("chroma_query"),
                "bm25_query": self.get_latency_stats("bm25_query"),
            },
        }

        file_path = self._output_dir / "storage_monitor_report.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info("保存监控报告: %s", file_path)
