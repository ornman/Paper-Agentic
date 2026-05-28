"""预处理 Pipeline 监控器

监控预处理 pipeline 的执行状态、耗时、日志。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("paper-assistant")


@dataclass
class StageMetrics:
    """阶段指标"""
    stage: str
    started_at: float = 0.0
    completed_at: float = 0.0
    duration_ms: int = 0
    status: str = "pending"  # pending / running / completed / failed / degraded
    error: str | None = None
    details: dict = field(default_factory=dict)


@dataclass
class PipelineMetrics:
    """Pipeline 指标"""
    task_id: str
    file_path: str
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    total_duration_ms: int = 0
    stages: dict[str, StageMetrics] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    status: str = "running"  # running / completed / failed / degraded


class PipelineMonitor:
    """Pipeline 监控器

    收集和记录预处理 pipeline 的执行指标。
    """

    def __init__(self, output_dir: str | None = None):
        """
        Args:
            output_dir: 指标输出目录
        """
        self._output_dir = Path(output_dir) if output_dir else None
        self._metrics: dict[str, PipelineMetrics] = {}

    def start_task(self, task_id: str, file_path: str):
        """开始监控任务"""
        self._metrics[task_id] = PipelineMetrics(
            task_id=task_id,
            file_path=file_path,
        )
        self._record_event(task_id, "task.started", {"file_path": file_path})

    def start_stage(self, task_id: str, stage: str):
        """开始阶段"""
        if task_id not in self._metrics:
            return

        metrics = self._metrics[task_id]
        metrics.stages[stage] = StageMetrics(
            stage=stage,
            started_at=time.time(),
            status="running",
        )
        self._record_event(task_id, f"{stage}.started")

    def complete_stage(self, task_id: str, stage: str, details: dict = None):
        """完成阶段"""
        if task_id not in self._metrics:
            return

        metrics = self._metrics[task_id]
        if stage not in metrics.stages:
            return

        stage_metrics = metrics.stages[stage]
        stage_metrics.completed_at = time.time()
        stage_metrics.duration_ms = int((stage_metrics.completed_at - stage_metrics.started_at) * 1000)
        stage_metrics.status = "completed"
        stage_metrics.details = details or {}

        self._record_event(task_id, f"{stage}.completed", {
            "duration_ms": stage_metrics.duration_ms,
            **(details or {}),
        })

    def fail_stage(self, task_id: str, stage: str, error: str):
        """阶段失败"""
        if task_id not in self._metrics:
            return

        metrics = self._metrics[task_id]
        if stage not in metrics.stages:
            return

        stage_metrics = metrics.stages[stage]
        stage_metrics.completed_at = time.time()
        stage_metrics.duration_ms = int((stage_metrics.completed_at - stage_metrics.started_at) * 1000)
        stage_metrics.status = "failed"
        stage_metrics.error = error

        self._record_event(task_id, f"{stage}.failed", {"error": error})

    def degrade_stage(self, task_id: str, stage: str, reason: str):
        """阶段降级"""
        if task_id not in self._metrics:
            return

        metrics = self._metrics[task_id]
        if stage not in metrics.stages:
            return

        stage_metrics = metrics.stages[stage]
        stage_metrics.status = "degraded"
        stage_metrics.details["degrade_reason"] = reason

        self._record_event(task_id, f"{stage}.degraded", {"reason": reason})

    def complete_task(self, task_id: str):
        """完成任务"""
        if task_id not in self._metrics:
            return

        metrics = self._metrics[task_id]
        metrics.completed_at = time.time()
        metrics.total_duration_ms = int((metrics.completed_at - metrics.started_at) * 1000)
        metrics.status = "completed"

        # 检查是否有降级阶段
        for stage_metrics in metrics.stages.values():
            if stage_metrics.status == "degraded":
                metrics.status = "degraded"
                break

        self._record_event(task_id, "task.completed", {
            "total_duration_ms": metrics.total_duration_ms,
            "status": metrics.status,
        })

        # 保存指标
        self._save_metrics(task_id)

    def fail_task(self, task_id: str, error: str):
        """任务失败"""
        if task_id not in self._metrics:
            return

        metrics = self._metrics[task_id]
        metrics.completed_at = time.time()
        metrics.total_duration_ms = int((metrics.completed_at - metrics.started_at) * 1000)
        metrics.status = "failed"

        self._record_event(task_id, "task.failed", {"error": error})

        # 保存指标
        self._save_metrics(task_id)

    def get_metrics(self, task_id: str) -> PipelineMetrics | None:
        """获取任务指标"""
        return self._metrics.get(task_id)

    def _record_event(self, task_id: str, event: str, data: dict = None):
        """记录事件"""
        if task_id not in self._metrics:
            return

        self._metrics[task_id].events.append({
            "timestamp": time.time(),
            "event": event,
            "data": data or {},
        })

        # 同时输出到日志
        logger.info("[%s] %s %s", task_id, event, data or {})

    def _save_metrics(self, task_id: str):
        """保存指标到文件"""
        if not self._output_dir:
            return

        self._output_dir.mkdir(parents=True, exist_ok=True)

        metrics = self._metrics.get(task_id)
        if not metrics:
            return

        # 转换为可序列化格式
        data = {
            "task_id": metrics.task_id,
            "file_path": metrics.file_path,
            "started_at": metrics.started_at,
            "completed_at": metrics.completed_at,
            "total_duration_ms": metrics.total_duration_ms,
            "status": metrics.status,
            "stages": {
                name: {
                    "stage": s.stage,
                    "started_at": s.started_at,
                    "completed_at": s.completed_at,
                    "duration_ms": s.duration_ms,
                    "status": s.status,
                    "error": s.error,
                    "details": s.details,
                }
                for name, s in metrics.stages.items()
            },
            "events": metrics.events,
        }

        file_path = self._output_dir / f"{task_id}_metrics.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("保存指标: %s", file_path)
