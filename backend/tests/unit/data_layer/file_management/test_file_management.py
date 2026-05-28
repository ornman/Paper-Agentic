"""File Management & Storage Monitor 模块测试

FILE-U01: 目录管理定向单测
SMON-U01: StorageMonitor 单测
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from app.data_layer.data_persistence.file_management import DirectoryManager
from app.data_layer.data_persistence.monitor import StorageMonitor


class TestFILEU01:
    """目录管理定向单测"""

    def test_create_document_dirs(self, tmp_dir):
        """创建文档目录"""
        manager = DirectoryManager(
            papers_dir=str(tmp_dir / "papers"),
            parsed_dir=str(tmp_dir / "parsed"),
            backups_dir=str(tmp_dir / "backups"),
        )
        manager.init()

        paths = manager.create_document_dirs("test_paper_001")
        assert paths.paper_dir.exists()
        assert paths.parsed_dir.exists()
        assert paths.images_dir.exists()

    def test_save_and_load_markdown(self, tmp_dir):
        """保存和加载 markdown"""
        manager = DirectoryManager(
            papers_dir=str(tmp_dir / "papers"),
            parsed_dir=str(tmp_dir / "parsed"),
            backups_dir=str(tmp_dir / "backups"),
        )
        manager.init()

        manager.save_markdown("paper1", "# Hello\n\nWorld", {"page_count": 5})
        loaded = manager.load_markdown("paper1")

        assert loaded is not None
        assert loaded["markdown"] == "# Hello\n\nWorld"
        assert loaded["metadata"]["page_count"] == 5

    def test_load_markdown_nonexistent(self, tmp_dir):
        """加载不存在的 markdown 返回 None"""
        manager = DirectoryManager(
            papers_dir=str(tmp_dir / "papers"),
            parsed_dir=str(tmp_dir / "parsed"),
            backups_dir=str(tmp_dir / "backups"),
        )
        manager.init()

        assert manager.load_markdown("nonexistent") is None

    def test_save_structured(self, tmp_dir):
        """保存结构化数据"""
        manager = DirectoryManager(
            papers_dir=str(tmp_dir / "papers"),
            parsed_dir=str(tmp_dir / "parsed"),
            backups_dir=str(tmp_dir / "backups"),
        )
        manager.init()

        structured = {"sections": [{"title": "摘要", "content": "..."}]}
        manager.save_structured("paper1", structured)

        paths = manager.get_document_paths("paper1")
        data = json.loads(paths.structured_path.read_text(encoding="utf-8"))
        assert data["sections"][0]["title"] == "摘要"

    def test_save_report(self, tmp_dir):
        """保存提取报告"""
        manager = DirectoryManager(
            papers_dir=str(tmp_dir / "papers"),
            parsed_dir=str(tmp_dir / "parsed"),
            backups_dir=str(tmp_dir / "backups"),
        )
        manager.init()

        report = {"route": "A", "chunks": 10, "success": True}
        manager.save_report("paper1", report)

        paths = manager.get_document_paths("paper1")
        data = json.loads(paths.report_path.read_text(encoding="utf-8"))
        assert data["route"] == "A"

    def test_backup_document(self, tmp_dir):
        """备份文档"""
        manager = DirectoryManager(
            papers_dir=str(tmp_dir / "papers"),
            parsed_dir=str(tmp_dir / "parsed"),
            backups_dir=str(tmp_dir / "backups"),
        )
        manager.init()

        # 先保存一些数据
        manager.save_markdown("paper1", "content", {})
        manager.backup_document("paper1")

        backups = list((tmp_dir / "backups").iterdir())
        assert len(backups) == 1
        assert backups[0].name.startswith("paper1_")

    def test_get_storage_stats(self, tmp_dir):
        """获取存储统计"""
        manager = DirectoryManager(
            papers_dir=str(tmp_dir / "papers"),
            parsed_dir=str(tmp_dir / "parsed"),
            backups_dir=str(tmp_dir / "backups"),
        )
        manager.init()

        stats = manager.get_storage_stats()
        assert "papers_count" in stats
        assert "parsed_count" in stats
        assert "papers_size_mb" in stats
        assert "parsed_size_mb" in stats


class TestSMONU01:
    """StorageMonitor 单测"""

    def test_record_latency(self):
        """记录延迟指标"""
        monitor = StorageMonitor()
        monitor.record_latency("embedding", 150, success=True)
        monitor.record_latency("embedding", 200, success=True)
        monitor.record_latency("embedding", 5000, success=False, error="超时")

        stats = monitor.get_latency_stats("embedding")
        assert stats["count"] == 3
        assert stats["success_rate"] == pytest.approx(2 / 3)

    def test_update_health(self):
        """更新健康状态"""
        monitor = StorageMonitor()
        monitor.update_health(chroma_doc_count=100, bm25_doc_count=50)

        health = monitor.get_health()
        assert health.chroma_doc_count == 100
        assert health.bm25_doc_count == 50

    def test_save_report(self, tmp_dir):
        """保存监控报告"""
        monitor = StorageMonitor(output_dir=str(tmp_dir))
        monitor.record_latency("embedding", 100)
        monitor.update_health(chroma_doc_count=50)
        monitor.save_report()

        report_path = tmp_dir / "storage_monitor_report.json"
        assert report_path.exists()

        data = json.loads(report_path.read_text(encoding="utf-8"))
        assert data["health"]["chroma_doc_count"] == 50
        assert "latency" in data

    def test_latency_stats_empty(self):
        """空指标返回零值"""
        monitor = StorageMonitor()
        stats = monitor.get_latency_stats("nonexistent")
        assert stats["count"] == 0
        assert stats["avg_ms"] == 0
