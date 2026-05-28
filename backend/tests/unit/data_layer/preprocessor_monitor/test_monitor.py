"""Preprocessor Monitor 模块测试

PMON-U01: 阶段方法定向单测
"""

from __future__ import annotations

import pytest
import time
import json
from pathlib import Path

from app.data_layer.PDF_preprocessor_data.monitor import PipelineMonitor


class TestPMONU01:
    """阶段方法定向单测"""

    def test_start_task(self):
        """start_task 创建指标记录"""
        monitor = PipelineMonitor()
        monitor.start_task("task1", "/tmp/test.pdf")

        metrics = monitor.get_metrics("task1")
        assert metrics is not None
        assert metrics.task_id == "task1"
        assert metrics.file_path == "/tmp/test.pdf"
        assert metrics.status == "running"

    def test_start_stage(self):
        """start_stage 记录阶段开始"""
        monitor = PipelineMonitor()
        monitor.start_task("task1", "/tmp/test.pdf")
        monitor.start_stage("task1", "probing")

        metrics = monitor.get_metrics("task1")
        assert "probing" in metrics.stages
        assert metrics.stages["probing"].status == "running"

    def test_complete_stage(self):
        """complete_stage 记录阶段完成"""
        monitor = PipelineMonitor()
        monitor.start_task("task1", "/tmp/test.pdf")
        monitor.start_stage("task1", "probing")
        time.sleep(0.01)
        monitor.complete_stage("task1", "probing", {"page_count": 10})

        metrics = monitor.get_metrics("task1")
        stage = metrics.stages["probing"]
        assert stage.status == "completed"
        assert stage.duration_ms > 0
        assert stage.details["page_count"] == 10

    def test_fail_stage(self):
        """fail_stage 记录阶段失败"""
        monitor = PipelineMonitor()
        monitor.start_task("task1", "/tmp/test.pdf")
        monitor.start_stage("task1", "vlm")
        monitor.fail_stage("task1", "vlm", "API 超时")

        metrics = monitor.get_metrics("task1")
        assert metrics.stages["vlm"].status == "failed"
        assert metrics.stages["vlm"].error == "API 超时"

    def test_degrade_stage(self):
        """degrade_stage 记录阶段降级"""
        monitor = PipelineMonitor()
        monitor.start_task("task1", "/tmp/test.pdf")
        monitor.start_stage("task1", "vlm")
        monitor.degrade_stage("task1", "vlm", "VLM API 不可用")

        metrics = monitor.get_metrics("task1")
        assert metrics.stages["vlm"].status == "degraded"
        assert metrics.stages["vlm"].details["degrade_reason"] == "VLM API 不可用"

    def test_complete_task(self, tmp_dir):
        """complete_task 记录任务完成并保存"""
        monitor = PipelineMonitor(output_dir=str(tmp_dir))
        monitor.start_task("task1", "/tmp/test.pdf")
        monitor.start_stage("task1", "probing")
        monitor.complete_stage("task1", "probing")
        monitor.complete_task("task1")

        metrics = monitor.get_metrics("task1")
        assert metrics.status == "completed"
        assert metrics.total_duration_ms >= 0  # fast execution may yield 0

        # 验证文件保存
        saved_file = tmp_dir / "task1_metrics.json"
        assert saved_file.exists()
        data = json.loads(saved_file.read_text(encoding="utf-8"))
        assert data["task_id"] == "task1"
        assert data["status"] == "completed"

    def test_fail_task(self, tmp_dir):
        """fail_task 记录任务失败并保存"""
        monitor = PipelineMonitor(output_dir=str(tmp_dir))
        monitor.start_task("task1", "/tmp/test.pdf")
        monitor.fail_task("task1", "转换失败")

        metrics = monitor.get_metrics("task1")
        assert metrics.status == "failed"

        saved_file = tmp_dir / "task1_metrics.json"
        assert saved_file.exists()

    def test_degraded_task_status(self):
        """有降级阶段时，任务状态为 degraded"""
        monitor = PipelineMonitor()
        monitor.start_task("task1", "/tmp/test.pdf")
        monitor.start_stage("task1", "vlm")
        monitor.degrade_stage("task1", "vlm", "降级原因")
        monitor.complete_task("task1")

        metrics = monitor.get_metrics("task1")
        assert metrics.status == "degraded"

    def test_get_metrics_nonexistent(self):
        """获取不存在的任务返回 None"""
        monitor = PipelineMonitor()
        assert monitor.get_metrics("nonexistent") is None
