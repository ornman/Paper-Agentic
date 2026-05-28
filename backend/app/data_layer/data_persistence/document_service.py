"""文档级 ingest/index/delete/rebuild 服务

将预处理层、持久化层、检索层的零件串成完整闭环。
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("paper-assistant")


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


class DocumentIngestService:
    """文档级 ingest/index/delete/rebuild 服务

    完整闭环：
    probe -> convert -> clean -> vlm -> chunk -> embed -> index -> persist
    """

    # MinerU 支持的文件类型
    SUPPORTED_SUFFIXES = {".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".ppt", ".xls"}

    def __init__(
        self,
        config,
        vector_index,
        keyword_index,
        soft_delete_manager,
        directory_manager,
        embedding_client=None,
    ):
        self._config = config
        self._vector_index = vector_index
        self._keyword_index = keyword_index
        self._soft_delete_manager = soft_delete_manager
        self._directory_manager = directory_manager
        self._embedding_client = embedding_client

    async def ingest_document(
        self,
        file_path: Path,
        paper_id: str | None = None,
    ) -> IngestResult:
        """完整闭环导入文档

        Args:
            file_path: 文件路径
            paper_id: 论文 ID（默认从文件名生成）

        Returns:
            IngestResult
        """
        t0 = time.perf_counter()
        logs: list[dict] = []

        if file_path.suffix.lower() not in self.SUPPORTED_SUFFIXES:
            return IngestResult(
                paper_id=paper_id or file_path.stem,
                success=False,
                error=f"不支持的文件格式: {file_path.suffix}，支持: {', '.join(sorted(self.SUPPORTED_SUFFIXES))}",
                elapsed_s=0.0,
                logs=[_log("error", f"不支持的文件格式: {file_path.suffix}")],
            )

        if not file_path.exists():
            return IngestResult(
                paper_id=paper_id or file_path.stem,
                success=False,
                error=f"文件不存在: {file_path}",
                elapsed_s=0.0,
                logs=[_log("error", f"文件不存在: {file_path}")],
            )

        # 生成 paper_id
        if paper_id is None:
            paper_id = self._generate_paper_id(file_path)

        logs.append(_log("info", f"开始导入文档: {file_path.name}", paper_id=paper_id))

        try:
            # 1. 创建目录，复制 PDF
            paths = self._directory_manager.create_document_dirs(paper_id)
            stored_path = self._directory_manager.copy_paper(file_path, paper_id)
            logs.append(_log("info", f"文件已复制: {stored_path}"))

            # 2. 运行 Pipeline
            from ..PDF_preprocessor_data.transfer.pipeline import PipelineOrchestrator

            orchestrator = PipelineOrchestrator(
                embedding_client=self._embedding_client,
                vector_index=self._vector_index,
                keyword_index=self._keyword_index,
            )
            state = await orchestrator.run(stored_path, output_dir=paths.images_dir)
            logs.extend([
                _log("info", f"Pipeline 完成: stage={state.stage.value}", stage=state.stage.value)
            ])

            if state.stage.value == "failed":
                return IngestResult(
                    paper_id=paper_id,
                    success=False,
                    error=state.error or "Pipeline 失败",
                    elapsed_s=round(time.perf_counter() - t0, 2),
                    logs=logs,
                )

            # 3. 获取结果
            chunks = getattr(state, "_chunks", [])
            final_markdown = getattr(state, "_final_markdown", "")
            conversion_result = getattr(state, "_conversion_result", None)
            vlm_result = getattr(state, "_vlm_result", None)

            # 4. 持久化 markdown.json
            metadata = {}
            if conversion_result:
                metadata = dict(conversion_result.metadata)
            metadata["doc_type"] = file_path.suffix.lstrip(".").lower()
            metadata["source_file_path"] = str(file_path)
            metadata["file_name"] = file_path.name
            self._directory_manager.save_markdown(paper_id, final_markdown, metadata)
            logs.append(_log("info", "markdown.json 已保存"))

            # 5. 持久化 structured.json
            structured = self._build_structured(paper_id, chunks, metadata, vlm_result)
            self._directory_manager.save_structured(paper_id, structured)
            logs.append(_log("info", "structured.json 已保存"))

            # 6. 持久化 extraction_report.json
            report = self._build_report(paper_id, state, chunks, metadata)
            self._directory_manager.save_report(paper_id, report)
            logs.append(_log("info", "extraction_report.json 已保存"))

            elapsed = round(time.perf_counter() - t0, 2)
            logs.append(_log("info", f"导入完成，共 {len(chunks)} 个 chunk，耗时 {elapsed}s"))

            return IngestResult(
                paper_id=paper_id,
                success=True,
                chunk_count=len(chunks),
                elapsed_s=elapsed,
                structured_path=str(paths.structured_path),
                report_path=str(paths.report_path),
                logs=logs,
            )

        except Exception as e:
            elapsed = round(time.perf_counter() - t0, 2)
            logs.append(_log("error", f"导入失败: {e}"))
            logger.error("文档导入失败 [%s]: %s", paper_id, e, exc_info=True)
            return IngestResult(
                paper_id=paper_id,
                success=False,
                error=str(e),
                elapsed_s=elapsed,
                logs=logs,
            )

    def delete_document(self, paper_id: str) -> None:
        """软删除文档

        标记为软删除，不立即从索引移除。
        真正的删除由 cleanup_expired 在保留期后执行。
        """
        self._soft_delete_manager.mark_deleted(paper_id)
        logger.info("文档已标记软删除: %s", paper_id)

    def hard_delete_document(self, paper_id: str) -> None:
        """硬删除文档

        从索引真正移除 + 删除文件目录。
        仅用于 maintenance/cleanup 场景。
        """
        self._vector_index.delete_paper(paper_id)
        self._keyword_index.delete_paper(paper_id)
        self._directory_manager.delete_document(paper_id)
        logger.info("文档已硬删除: %s", paper_id)

    async def rebuild_document(self, paper_id: str) -> IngestResult:
        """重建文档索引（原子性）

        策略：rename 是 get+upsert+delete，upsert 不删旧条目。
        1. ingest 到 tmp_id
        2. rename tmp_id → backup_id（additive，旧索引不受影响）
        3. rename old_id → paper_id（additive，旧条目被覆盖）
        4. 成功后 delete backup_id（清理旧条目）
        任何步骤失败 → 旧索引数据保留。
        """
        # 备份
        self._directory_manager.backup_document(paper_id)

        # 找到原始文件（支持所有 MinerU 支持的格式）
        paper_dir = self._directory_manager._papers_dir / paper_id
        source_files = [
            f for f in paper_dir.iterdir()
            if f.is_file() and f.suffix.lower() in self.SUPPORTED_SUFFIXES
        ]
        if not source_files:
            return IngestResult(
                paper_id=paper_id,
                success=False,
                error=f"找不到原始文件: {paper_dir}",
            )

        # 用临时 paper_id 先建新索引，失败不影响旧索引
        tmp_id = f"{paper_id}__rebuild_tmp"
        backup_id = f"{paper_id}__rebuild_backup"
        result = await self.ingest_document(source_files[0], paper_id=tmp_id)

        if not result.success:
            self._vector_index.delete_paper(tmp_id)
            self._keyword_index.delete_paper(tmp_id)
            self._cleanup_tmp_dirs(tmp_id)
            logger.error("重建失败，旧索引保留: %s, error=%s", paper_id, result.error)
            return IngestResult(
                paper_id=paper_id,
                success=False,
                error=result.error,
                elapsed_s=result.elapsed_s,
                logs=result.logs,
            )

        # 新索引构建成功，开始原子替换
        # Step 1: rename tmp → backup（additive，不删旧条目）
        try:
            self._vector_index.rename_paper(tmp_id, backup_id)
            self._keyword_index.rename_paper(tmp_id, backup_id)
        except Exception as e:
            self._vector_index.delete_paper(tmp_id)
            self._keyword_index.delete_paper(tmp_id)
            self._cleanup_tmp_dirs(tmp_id)
            logger.error("rename tmp→backup 失败，旧索引保留: %s, error=%s", paper_id, e)
            return IngestResult(
                paper_id=paper_id, success=False, error=f"rename tmp→backup 失败: {e}",
                elapsed_s=result.elapsed_s, logs=result.logs,
            )

        # Step 2: rename backup → paper_id（upsert 覆盖旧条目，delete 清理 backup）
        # 如果失败：旧条目还在 paper_id 下（未被修改），backup 有新数据（可忽略）
        try:
            self._vector_index.rename_paper(backup_id, paper_id)
            self._keyword_index.rename_paper(backup_id, paper_id)
        except Exception as e:
            self._vector_index.delete_paper(backup_id)
            self._keyword_index.delete_paper(backup_id)
            self._cleanup_tmp_dirs(tmp_id)
            logger.error("rename backup→final 失败，旧索引保留: %s, error=%s", paper_id, e)
            return IngestResult(
                paper_id=paper_id, success=False, error=f"rename backup→final 失败: {e}",
                elapsed_s=result.elapsed_s, logs=result.logs,
            )

        # Step 3: 清理 backup 条目和临时目录
        self._vector_index.delete_paper(backup_id)
        self._keyword_index.delete_paper(backup_id)
        self._cleanup_tmp_dirs(tmp_id)

        paths = self._directory_manager.get_document_paths(paper_id)
        logger.info("重建成功: %s", paper_id)
        return IngestResult(
            paper_id=paper_id,
            success=True,
            chunk_count=result.chunk_count,
            elapsed_s=result.elapsed_s,
            structured_path=str(paths.structured_path),
            report_path=str(paths.report_path),
            logs=result.logs,
        )

    def list_documents(self) -> list[dict]:
        """列出所有已导入文档及其状态"""
        docs = []
        papers_dir = self._directory_manager._papers_dir
        if not papers_dir.exists():
            return docs

        for paper_dir in papers_dir.iterdir():
            if not paper_dir.is_dir():
                continue

            paper_id = paper_dir.name
            is_deleted = self._soft_delete_manager.is_deleted(paper_id)

            parsed_dir = self._directory_manager._parsed_dir / paper_id
            has_parsed = parsed_dir.exists()

            files = [
                f.name for f in paper_dir.iterdir()
                if f.is_file() and f.suffix.lower() in self.SUPPORTED_SUFFIXES
            ]

            docs.append({
                "paper_id": paper_id,
                "is_deleted": is_deleted,
                "has_parsed": has_parsed,
                "files": files,
            })

        return docs

    def _cleanup_tmp_dirs(self, tmp_id: str) -> None:
        """清理 rebuild 临时目录（papers + parsed）"""
        import shutil
        for base_dir in (self._directory_manager._papers_dir, self._directory_manager._parsed_dir):
            tmp_dir = base_dir / tmp_id
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def _generate_paper_id(self, file_path: Path) -> str:
        """从文件路径生成 paper_id"""
        name = file_path.stem
        # 如果文件名太长，用 hash 截断
        if len(name) > 50:
            h = hashlib.md5(name.encode()).hexdigest()[:8]
            name = f"{name[:40]}_{h}"
        return name

    def _build_structured(
        self,
        paper_id: str,
        chunks: list,
        metadata: dict,
        vlm_result=None,
    ) -> dict:
        """构建 structured.json"""
        anchors = []
        for i, chunk in enumerate(chunks):
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

        paths = self._directory_manager.get_document_paths(paper_id)

        return {
            "document_id": paper_id,
            "paper_id": paper_id,
            "doc_type": metadata.get("doc_type", "pdf"),
            "source_file_path": metadata.get("source_file_path", ""),
            "pipeline_version": "v4",
            "markdown_path": str(paths.markdown_path),
            "images_dir": str(paths.images_dir),
            "doc_level": {
                "file_name": metadata.get("file_name", ""),
                "page_count": metadata.get("page_count", 0),
                "route": metadata.get("route", ""),
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
        self,
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
            "route": state.route.value if state.route else None,
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
    """为 visual_blocks 解析真实的 parent_anchor_id

    匹配策略：按 page + bbox 空间距离找最近的 anchor。
    """
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
