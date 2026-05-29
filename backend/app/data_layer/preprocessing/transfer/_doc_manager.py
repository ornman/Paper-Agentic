"""文档生命周期管理

职责：文档 CRUD（ingest/delete/hard_delete/rebuild/list）+ 制品持久化。
不负责流水线执行。
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

from .pipeline import (
    IngestResult,
    PipelineState,
    PipelineStage,
    StageResults,
    SUPPORTED_SUFFIXES,
    _build_structured,
    _build_report,
    _generate_paper_id,
    _log,
)

logger = logging.getLogger("paper-assistant")


class DocumentManager:
    """文档生命周期管理"""

    def __init__(
        self,
        directory_manager=None,
        soft_delete_manager=None,
        vector_index=None,
        keyword_index=None,
    ):
        self._directory_manager = directory_manager
        self._soft_delete_manager = soft_delete_manager
        self._vector_index = vector_index
        self._keyword_index = keyword_index

    async def ingest(
        self,
        file_path: Path,
        paper_id: str | None,
        run_fn,
    ) -> IngestResult:
        """完整导入流程：验证 → 复制 → 执行流水线 → 持久化制品"""
        t0 = time.perf_counter()
        logs: list[dict] = []

        if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            return IngestResult(
                paper_id=paper_id or file_path.stem,
                success=False,
                error=f"不支持的文件格式: {file_path.suffix}，支持: {', '.join(sorted(SUPPORTED_SUFFIXES))}",
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

        if paper_id is None:
            paper_id = _generate_paper_id(file_path)

        logs.append(_log("info", f"开始导入文档: {file_path.name}", paper_id=paper_id))

        try:
            # 1. 创建目录，复制文件
            dm = self._directory_manager
            if dm is not None:
                paths = dm.create_document_dirs(paper_id)
                stored_path = dm.copy_paper(file_path, paper_id)
                images_dir = paths.images_dir
                logs.append(_log("info", f"文件已复制: {stored_path}"))
            else:
                stored_path = file_path
                images_dir = None

            # 2. 运行 Pipeline
            state = await run_fn(stored_path, output_dir=images_dir)
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
            chunks = state.results.chunks or []
            final_markdown = state.results.final_markdown or ""
            conversion_result = state.results.conversion
            vlm_result = state.results.vlm

            # 4. 持久化产物
            if dm is not None:
                metadata = {}
                if conversion_result:
                    metadata = dict(conversion_result.metadata)
                metadata["doc_type"] = file_path.suffix.lstrip(".").lower()
                metadata["source_file_path"] = str(file_path)
                metadata["file_name"] = file_path.name
                dm.save_markdown(paper_id, final_markdown, metadata)
                logs.append(_log("info", "markdown.json 已保存"))

                structured = _build_structured(paper_id, chunks, metadata, vlm_result, dm)
                dm.save_structured(paper_id, structured)
                logs.append(_log("info", "structured.json 已保存"))

                report = _build_report(paper_id, state, chunks, metadata)
                dm.save_report(paper_id, report)
                logs.append(_log("info", "extraction_report.json 已保存"))

                result_paths = dm.get_document_paths(paper_id)
                structured_path = str(result_paths.structured_path)
                report_path = str(result_paths.report_path)
            else:
                structured_path = None
                report_path = None

            elapsed = round(time.perf_counter() - t0, 2)
            logs.append(_log("info", f"导入完成，共 {len(chunks)} 个 chunk，耗时 {elapsed}s"))

            return IngestResult(
                paper_id=paper_id,
                success=True,
                chunk_count=len(chunks),
                elapsed_s=elapsed,
                structured_path=structured_path,
                report_path=report_path,
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

    def delete(self, paper_id: str) -> None:
        """软删除文档"""
        if self._soft_delete_manager is None:
            raise RuntimeError("soft_delete_manager 未配置")
        self._soft_delete_manager.mark_deleted(paper_id)
        logger.info("文档已标记软删除: %s", paper_id)

    def hard_delete(self, paper_id: str) -> None:
        """硬删除文档（索引 + 文件）"""
        if self._vector_index:
            self._vector_index.delete_paper(paper_id)
        if self._keyword_index:
            self._keyword_index.delete_paper(paper_id)
        if self._directory_manager:
            self._directory_manager.delete_document(paper_id)
        logger.info("文档已硬删除: %s", paper_id)

    async def rebuild(self, paper_id: str, run_fn) -> IngestResult:
        """重建文档索引（原子性）

        策略：ingest 到 tmp_id → rename tmp→backup → rename backup→paper_id → 清理
        """
        dm = self._directory_manager
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
        result = await self.ingest(source_files[0], paper_id=tmp_id, run_fn=run_fn)

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

        # rename tmp → backup
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

        # rename backup → paper_id
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

        # 清理
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
        """列出所有已导入文档及其状态"""
        dm = self._directory_manager
        if dm is None:
            return []

        docs = []
        papers_dir = dm._papers_dir
        if not papers_dir.exists():
            return docs

        for paper_dir in papers_dir.iterdir():
            if not paper_dir.is_dir():
                continue
            paper_id = paper_dir.name
            is_deleted = (
                self._soft_delete_manager.is_deleted(paper_id)
                if self._soft_delete_manager else False
            )
            parsed_dir = dm._parsed_dir / paper_id
            has_parsed = parsed_dir.exists()
            files = [
                f.name for f in paper_dir.iterdir()
                if f.is_file() and f.suffix.lower() in SUPPORTED_SUFFIXES
            ]
            docs.append({
                "paper_id": paper_id,
                "is_deleted": is_deleted,
                "has_parsed": has_parsed,
                "files": files,
            })

        return docs


def _cleanup_tmp_dirs(directory_manager, tmp_id: str) -> None:
    """清理 rebuild 临时目录"""
    for base_dir in (directory_manager._papers_dir, directory_manager._parsed_dir):
        tmp_dir = base_dir / tmp_id
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
