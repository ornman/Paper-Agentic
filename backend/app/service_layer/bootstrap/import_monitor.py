"""ImportMonitor — 导入链路统一调度层

两种受众：
1. 开发者：PipelineMonitor 阶段耗时 + StorageMonitor 延迟/健康
2. 用户：SSE 实时进度 + 中间产物（markdown/structured/report）查询

pipeline 只管 emit，不关心谁在监听。ImportMonitor 是唯一的调度入口。
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger("paper-assistant")

# ── 阶段权重（进度百分比）──────────────────────────────────────
_STAGE_WEIGHTS = {
    "transforming": 25,
    "vlm_enriching": 10,
    "cleaning": 10,
    "chunking": 15,
    "embedding": 20,
    "indexing": 20,
}


class ImportMonitor:
    """导入链路统一监控器

    职责：
    - 接收 pipeline 事件，分发到 SSE bus（用户）和 monitor（开发者）
    - 提供中间产物查询接口（给 Agent / 前端）
    """

    def __init__(self, progress_bus, pipeline_monitor=None, storage_monitor=None):
        self._bus = progress_bus
        self._pipeline_monitor = pipeline_monitor
        self._storage_monitor = storage_monitor
        # task_id -> {stage, percent, started_at, events}
        self._tasks: dict[str, dict] = {}

    # ── 供 PipelineOrchestrator 使用的回调 ─────────────────────

    def on_pipeline_event(self, event) -> None:
        """接收 PipelineEvent，统一分发"""
        task_id = event.task_id
        event_name = event.event
        stage = event.stage.value if hasattr(event.stage, "value") else str(event.stage)
        data = event.data if hasattr(event, "data") else {}

        # 初始化 task 追踪
        if task_id not in self._tasks:
            self._tasks[task_id] = {
                "stage": stage,
                "percent": 0,
                "started_at": time.time(),
                "events": [],
            }
        task = self._tasks[task_id]
        task["stage"] = stage
        task["events"].append({
            "event": event_name,
            "stage": stage,
            "message": event.message,
            "data": data,
            "timestamp": event.timestamp if hasattr(event, "timestamp") else time.time(),
        })

        # 计算进度
        percent = _calc_percent(event_name, stage, data)
        task["percent"] = percent

        # 1. 推 SSE（用户侧）
        self._publish_sse(task_id, event_name, stage, percent, data, event.message)

        # 2. 桥接 PipelineMonitor（开发者侧）
        self._bridge_pipeline_monitor(task_id, event_name, stage, data)

    # ── SSE 发布 ──────────────────────────────────────────────

    def _publish_sse(
        self,
        task_id: str,
        event_name: str,
        stage: str,
        percent: int,
        data: dict,
        message: str,
    ) -> None:
        """发布进度到 SSE bus"""
        import asyncio

        payload = {
            "status": "running",
            "step": stage,
            "percent": percent,
            "stage_name": _STAGE_LABELS.get(stage, stage),
            "message": message,
            "paper_id": None,
        }
        if data:
            payload["detail"] = data

        if event_name.endswith(".completed"):
            payload["status"] = "stage_done"
        elif event_name.endswith(".failed"):
            payload["status"] = "stage_failed"
            payload["error_msg"] = data.get("error", "")
        elif event_name == "pipeline.completed":
            payload["status"] = "completed"
            payload["percent"] = 100
        elif event_name == "pipeline.failed":
            payload["status"] = "failed"
            payload["error_msg"] = data.get("error", message)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._bus.publish(task_id, payload))
            else:
                loop.run_until_complete(self._bus.publish(task_id, payload))
        except RuntimeError:
            # 非 async 上下文，跳过 SSE（dev 模式）
            pass

    # ── PipelineMonitor 桥接（开发者指标）──────────────────────

    def _bridge_pipeline_monitor(
        self, task_id: str, event_name: str, stage: str, data: dict
    ) -> None:
        """将事件桥接到 PipelineMonitor 记录指标"""
        monitor = self._pipeline_monitor
        if monitor is None:
            return

        # 阶段开始
        if event_name.endswith(".started") and not event_name.startswith("pipeline"):
            monitor.start_stage(task_id, stage)

        # 阶段完成
        elif event_name.endswith(".completed") and not event_name.startswith("pipeline"):
            monitor.complete_stage(task_id, stage, details=data)

        # 阶段失败
        elif event_name.endswith(".failed") and not event_name.startswith("pipeline"):
            monitor.fail_stage(task_id, stage, data.get("error", "unknown"))

        # 降级
        elif event_name == "pipeline.degraded":
            monitor.degrade_stage(task_id, stage, reason=data.get("reason", "degraded"))

        # 任务级
        elif event_name == "pipeline.completed":
            monitor.complete_task(task_id)
        elif event_name == "pipeline.failed":
            monitor.fail_task(task_id, data.get("error", "unknown"))

    # ── 中间产物查询 ──────────────────────────────────────────

    def get_progress(self, task_id: str) -> dict | None:
        """获取任务进度快照"""
        task = self._tasks.get(task_id)
        if not task:
            return None
        return {
            "task_id": task_id,
            "stage": task["stage"],
            "percent": task["percent"],
            "stage_name": _STAGE_LABELS.get(task["stage"], task["stage"]),
            "elapsed_s": round(time.time() - task["started_at"], 1),
        }

    def get_artifacts(self, task_id: str, directory_manager) -> dict | None:
        """获取中间产物路径和摘要（供 Agent / 前端查询）"""
        if not directory_manager:
            return None

        try:
            paths = directory_manager.get_document_paths(task_id)
        except Exception:
            return None

        result: dict = {"paper_id": task_id, "files": {}}

        # markdown.json
        md_path = Path(paths.markdown_path) if hasattr(paths, "markdown_path") else None
        if md_path and md_path.exists():
            try:
                md_data = json.loads(md_path.read_text(encoding="utf-8"))
                result["files"]["markdown"] = {
                    "path": str(md_path),
                    "char_count": len(md_data.get("markdown", "")),
                    "metadata_keys": list(md_data.get("metadata", {}).keys()),
                }
            except Exception:
                result["files"]["markdown"] = {"path": str(md_path)}

        # structured.json
        st_path = Path(paths.structured_path) if hasattr(paths, "structured_path") else None
        if st_path and st_path.exists():
            try:
                st_data = json.loads(st_path.read_text(encoding="utf-8"))
                chunks = st_data.get("chunks", [])
                result["files"]["structured"] = {
                    "path": str(st_path),
                    "chunk_count": len(chunks),
                    "sections": list({c.get("section_title", "") for c in chunks if c.get("section_title")}),
                }
            except Exception:
                result["files"]["structured"] = {"path": str(st_path)}

        # extraction_report.json
        rp_path = Path(paths.report_path) if hasattr(paths, "report_path") else None
        if rp_path and rp_path.exists():
            try:
                rp_data = json.loads(rp_path.read_text(encoding="utf-8"))
                result["files"]["report"] = {
                    "path": str(rp_path),
                    "total_chunks": rp_data.get("total_chunks", 0),
                    "total_chars": rp_data.get("total_chars", 0),
                    "stages": rp_data.get("stages", {}),
                }
            except Exception:
                result["files"]["report"] = {"path": str(rp_path)}

        return result


# ── 进度计算 ──────────────────────────────────────────────────

def _calc_percent(event_name: str, stage: str, data: dict) -> int:
    """根据阶段和事件类型计算进度百分比"""
    if event_name == "pipeline.completed":
        return 100
    if event_name == "pipeline.failed":
        return -1

    base = sum(_STAGE_WEIGHTS[s] for s in _STAGE_ORDER if _STAGE_ORDER.index(s) < _STAGE_ORDER.index(stage)) if stage in _STAGE_ORDER else 0

    if event_name.endswith(".started"):
        return base
    elif event_name.endswith(".completed"):
        return base + _STAGE_WEIGHTS.get(stage, 0)
    elif event_name.endswith(".failed"):
        return base + _STAGE_WEIGHTS.get(stage, 0) // 2

    # MinerU 进度
    if "extracted_pages" in data and "total_pages" in data:
        total = data["total_pages"]
        if total > 0:
            stage_progress = data["extracted_pages"] / total
            return base + int(_STAGE_WEIGHTS.get(stage, 0) * stage_progress)

    return base


# ── 常量 ──────────────────────────────────────────────────────

_STAGE_ORDER = [
    "transforming",
    "vlm_enriching",
    "cleaning",
    "chunking",
    "embedding",
    "indexing",
]

_STAGE_LABELS = {
    "transforming": "PDF 解析",
    "vlm_enriching": "图片理解",
    "cleaning": "内容清洗",
    "chunking": "语义切分",
    "embedding": "向量化",
    "indexing": "建立索引",
    "queued": "排队中",
    "done": "完成",
    "failed": "失败",
    "degraded": "降级完成",
}
