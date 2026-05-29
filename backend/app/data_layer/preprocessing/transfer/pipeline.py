"""预处理 Pipeline 模块

数据类型 + PipelineOrchestrator 门面（转发调用到 PipelineRunner + DocumentManager）。
纯函数（_build_structured 等）保留在本文件。

外部 API 不变：PipelineOrchestrator, PipelineState, PipelineStage, PipelineEvent, IngestResult。
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger("paper-assistant")

# 当前仅支持 PDF（其他格式需验证清洗策略后再放行）
SUPPORTED_SUFFIXES = {".pdf"}


# ── 数据类型 ──────────────────────────────────────────────────


class PipelineStage(str, Enum):
    """Pipeline 阶段"""
    QUEUED = "queued"
    TRANSFORMING = "transforming"
    CLEANING = "cleaning"
    VLM_ENRICHING = "vlm_enriching"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    DONE = "done"
    FAILED = "failed"
    DEGRADED = "degraded"


@dataclass
class PipelineEvent:
    """Pipeline 事件"""
    event: str
    stage: PipelineStage
    task_id: str
    message: str
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class StageResults:
    """各阶段产出（替代动态属性 state._xxx）"""
    conversion: object | None = None
    cleaning: object | None = None
    vlm: object | None = None
    chunks: list | None = None
    final_markdown: str | None = None
    vectors: list | None = None


@dataclass
class PipelineState:
    """Pipeline 状态"""
    task_id: str
    file_path: Path
    stage: PipelineStage = PipelineStage.QUEUED
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    events: list[PipelineEvent] = field(default_factory=list)
    results: StageResults = field(default_factory=StageResults)

    # ── 向后兼容属性（测试/外部代码仍可用 state._chunks 等）──

    @property
    def _conversion_result(self):
        return self.results.conversion

    @_conversion_result.setter
    def _conversion_result(self, v):
        self.results.conversion = v

    @property
    def _cleaning_result(self):
        return self.results.cleaning

    @_cleaning_result.setter
    def _cleaning_result(self, v):
        self.results.cleaning = v

    @property
    def _vlm_result(self):
        return self.results.vlm

    @_vlm_result.setter
    def _vlm_result(self, v):
        self.results.vlm = v

    @property
    def _chunks(self):
        return self.results.chunks

    @_chunks.setter
    def _chunks(self, v):
        self.results.chunks = v

    @property
    def _final_markdown(self):
        return self.results.final_markdown

    @_final_markdown.setter
    def _final_markdown(self, v):
        self.results.final_markdown = v

    @property
    def _vectors(self):
        return self.results.vectors

    @_vectors.setter
    def _vectors(self, v):
        self.results.vectors = v


@dataclass
class IngestResult:
    """文档导入结果"""
    paper_id: str
    success: bool
    error: str | None = None
    chunk_count: int = 0
    elapsed_s: float = 0.0
    structured_path: str | None = None
    report_path: str | None = None
    logs: list[dict] = field(default_factory=list)


# ── 门面 ──────────────────────────────────────────────────────


class PipelineOrchestrator:
    """Pipeline 编排器（门面）

    唯一入口：文档导入、删除、重建、列表。
    内部委托给 PipelineRunner（流水线执行）+ DocumentManager（文档 CRUD）。
    """

    def __init__(
        self,
        monitor_callback=None,
        *,
        embedding_client=None,
        vector_index=None,
        keyword_index=None,
        directory_manager=None,
        soft_delete_manager=None,
        pipeline_monitor=None,
        storage_monitor=None,
    ):
        self._embedding_client = embedding_client
        self._vector_index = vector_index
        self._keyword_index = keyword_index

        from ._stages import PipelineRunner
        from ._doc_manager import DocumentManager

        self._runner = PipelineRunner(
            pipeline_monitor=pipeline_monitor,
            storage_monitor=storage_monitor,
            monitor_callback=monitor_callback,
        )
        self._doc_mgr = DocumentManager(
            directory_manager=directory_manager,
            soft_delete_manager=soft_delete_manager,
            vector_index=vector_index,
            keyword_index=keyword_index,
        )

    # ── 文档级操作 ────────────────────────────────────────────

    async def ingest_document(self, file_path: Path, paper_id: str | None = None) -> IngestResult:
        return await self._doc_mgr.ingest(file_path, paper_id, self.run)

    def delete_document(self, paper_id: str) -> None:
        self._doc_mgr.delete(paper_id)

    def hard_delete_document(self, paper_id: str) -> None:
        self._doc_mgr.hard_delete(paper_id)

    async def rebuild_document(self, paper_id: str) -> IngestResult:
        """重建文档索引（原子性）

        策略：ingest 到 tmp_id → rename tmp→backup → rename backup→paper_id → 清理
        注意：直接调用 self.ingest_document（非 _doc_mgr.ingest），保证测试 mock 可截获。
        """
        from ._doc_manager import _cleanup_tmp_dirs

        dm = self._doc_mgr._directory_manager
        if dm is None:
            return IngestResult(paper_id=paper_id, success=False, error="directory_manager 未配置")

        dm.backup_document(paper_id)

        paper_dir = dm._papers_dir / paper_id
        source_files = [
            f for f in paper_dir.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_SUFFIXES
        ]
        if not source_files:
            return IngestResult(paper_id=paper_id, success=False, error=f"找不到原始文件: {paper_dir}")

        tmp_id = f"{paper_id}__rebuild_tmp"
        backup_id = f"{paper_id}__rebuild_backup"
        result = await self.ingest_document(source_files[0], paper_id=tmp_id)

        if not result.success:
            if self._vector_index:
                self._vector_index.delete_paper(tmp_id)
            if self._keyword_index:
                self._keyword_index.delete_paper(tmp_id)
            _cleanup_tmp_dirs(dm, tmp_id)
            logger.error("重建失败，旧索引保留: %s, error=%s", paper_id, result.error)
            return IngestResult(
                paper_id=paper_id, success=False, error=result.error,
                elapsed_s=result.elapsed_s, logs=result.logs,
            )

        try:
            if self._vector_index:
                self._vector_index.rename_paper(tmp_id, backup_id)
            if self._keyword_index:
                self._keyword_index.rename_paper(tmp_id, backup_id)
        except Exception as e:
            if self._vector_index:
                self._vector_index.delete_paper(tmp_id)
            if self._keyword_index:
                self._keyword_index.delete_paper(tmp_id)
            _cleanup_tmp_dirs(dm, tmp_id)
            logger.error("rename tmp→backup 失败: %s, %s", paper_id, e)
            return IngestResult(
                paper_id=paper_id, success=False, error=f"rename tmp→backup 失败: {e}",
                elapsed_s=result.elapsed_s, logs=result.logs,
            )

        try:
            if self._vector_index:
                self._vector_index.rename_paper(backup_id, paper_id)
            if self._keyword_index:
                self._keyword_index.rename_paper(backup_id, paper_id)
        except Exception as e:
            if self._vector_index:
                self._vector_index.delete_paper(backup_id)
            if self._keyword_index:
                self._keyword_index.delete_paper(backup_id)
            _cleanup_tmp_dirs(dm, tmp_id)
            logger.error("rename backup→final 失败: %s, %s", paper_id, e)
            return IngestResult(
                paper_id=paper_id, success=False, error=f"rename backup→final 失败: {e}",
                elapsed_s=result.elapsed_s, logs=result.logs,
            )

        if self._vector_index:
            self._vector_index.delete_paper(backup_id)
        if self._keyword_index:
            self._keyword_index.delete_paper(backup_id)
        _cleanup_tmp_dirs(dm, tmp_id)

        logger.info("重建成功: %s", paper_id)
        return IngestResult(
            paper_id=paper_id,
            success=True,
            chunk_count=result.chunk_count,
            elapsed_s=result.elapsed_s,
            structured_path=result.structured_path,
            report_path=result.report_path,
            logs=result.logs,
        )

    def list_documents(self) -> list[dict]:
        return self._doc_mgr.list_documents()

    # ── 流水线 ────────────────────────────────────────────────

    async def run(self, file_path: Path, output_dir: Path | None = None) -> PipelineState:
        return await self._runner.run(
            file_path,
            output_dir,
            embedding_client=self._embedding_client,
            vector_index=self._vector_index,
            keyword_index=self._keyword_index,
        )

    def get_state(self, task_id: str) -> PipelineState | None:
        return self._runner.get_state(task_id)

    # ── 向后兼容属性（测试直接访问 _soft_delete_manager 等）──

    @property
    def _soft_delete_manager(self):
        return self._doc_mgr._soft_delete_manager

    @property
    def _directory_manager(self):
        return self._doc_mgr._directory_manager


# ── 纯函数 ────────────────────────────────────────────────────


def _generate_paper_id(file_path: Path) -> str:
    """从文件路径生成 paper_id"""
    name = file_path.stem
    if len(name) > 50:
        h = hashlib.md5(name.encode()).hexdigest()[:8]
        name = f"{name[:40]}_{h}"
    return name


def _build_structured(
    paper_id: str,
    chunks: list,
    metadata: dict,
    vlm_result=None,
    directory_manager=None,
) -> dict:
    """构建 structured.json"""
    anchors = []
    for chunk in chunks:
        for anchor in chunk.anchors:
            anchors.append({
                "anchor_id": anchor.anchor_id,
                "source_file_path": anchor.source_file_path,
                "doc_type": anchor.doc_type,
                "page": anchor.page,
                "block_id": anchor.block_id,
                "block_type": anchor.block_type,
                "heading_path": anchor.heading_path,
                "paragraph_index": anchor.paragraph_index,
                "char_start": anchor.char_start,
                "char_end": anchor.char_end,
                "bbox": anchor.bbox,
                "parent_anchor_id": anchor.parent_anchor_id,
                "source_text_hash": anchor.source_text_hash,
            })

    visual_blocks = []
    if vlm_result and hasattr(vlm_result, "visual_blocks"):
        visual_blocks = _resolve_visual_block_anchors(
            vlm_result.visual_blocks, chunks, anchors,
        )

    paths = directory_manager.get_document_paths(paper_id) if directory_manager else None

    return {
        "document_id": paper_id,
        "paper_id": paper_id,
        "doc_type": metadata.get("doc_type", "pdf"),
        "source_file_path": metadata.get("source_file_path", ""),
        "pipeline_version": "v4",
        "markdown_path": str(paths.markdown_path) if paths else "",
        "images_dir": str(paths.images_dir) if paths else "",
        "doc_level": {
            "file_name": metadata.get("file_name", ""),
            "page_count": metadata.get("page_count", 0),
            "char_count": metadata.get("char_count", 0),
        },
        "anchors": anchors,
        "visual_blocks": visual_blocks,
        "stats": {
            "chunk_count": len(chunks),
            "anchor_count": len(anchors),
            "visual_block_count": len(visual_blocks),
        },
    }


def _build_report(
    paper_id: str,
    state,
    chunks: list,
    metadata: dict,
) -> dict:
    """构建 extraction_report.json"""
    events = [
        {
            "event": e.event,
            "stage": e.stage.value,
            "message": e.message,
            "timestamp": e.timestamp,
        }
        for e in state.events
    ]

    return {
        "paper_id": paper_id,
        "status": state.stage.value,
        "error": state.error,
        "started_at": state.started_at,
        "completed_at": state.completed_at,
        "elapsed_s": round(state.completed_at - state.started_at, 2) if state.completed_at else 0,
        "chunk_count": len(chunks),
        "metadata": metadata,
        "events": events,
    }


def _resolve_visual_block_anchors(
    visual_blocks: list[dict],
    chunks: list,
    anchors: list[dict],
) -> list[dict]:
    """为 visual_blocks 解析真实的 parent_anchor_id"""
    resolved = []
    for vb in visual_blocks:
        if vb.get("parent_anchor_id"):
            resolved.append(vb)
            continue

        vb_page = vb.get("page", 0)
        vb_bbox = vb.get("bbox", [])
        best_anchor_id = ""
        best_score = float("inf")

        for anchor_dict in anchors:
            a_page = anchor_dict.get("page", 0)
            if a_page and vb_page and a_page != vb_page:
                continue

            a_bbox = anchor_dict.get("bbox", [])
            if vb_bbox and a_bbox and len(vb_bbox) >= 4 and len(a_bbox) >= 4:
                dist = sum((a - b) ** 2 for a, b in zip(vb_bbox[:4], a_bbox[:4])) ** 0.5
            else:
                dist = 0 if a_page == vb_page else 9999

            if dist < best_score:
                best_score = dist
                best_anchor_id = anchor_dict.get("anchor_id", "")

        new_vb = dict(vb)
        new_vb["parent_anchor_id"] = best_anchor_id
        resolved.append(new_vb)

    return resolved


def _log(level: str, message: str, **kwargs) -> dict:
    """生成日志条目"""
    import datetime
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "level": level,
        "message": message,
    }
    entry.update(kwargs)
    return entry
