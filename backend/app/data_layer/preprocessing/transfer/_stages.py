"""Pipeline 4 阶段执行器

职责：transform → clean → vlm → chunk → embed → index。
不负责文档 CRUD、制品构建。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from pathlib import Path

from .pipeline import PipelineState, PipelineStage, PipelineEvent, StageResults

logger = logging.getLogger("paper-assistant")


class PipelineRunner:
    """4 阶段流水线执行器"""

    def __init__(self, pipeline_monitor=None, storage_monitor=None, monitor_callback=None):
        self._pipeline_monitor = pipeline_monitor
        self._storage_monitor = storage_monitor
        self._monitor_callback = monitor_callback
        self._states: dict[str, PipelineState] = {}

    async def run(
        self,
        file_path: Path,
        output_dir: Path | None = None,
        *,
        embedding_client=None,
        vector_index=None,
        keyword_index=None,
    ) -> PipelineState:
        """执行 4 阶段流水线"""
        task_id = str(uuid.uuid4())[:8]
        state = PipelineState(task_id=task_id, file_path=file_path)
        self._states[task_id] = state

        if self._pipeline_monitor:
            self._pipeline_monitor.start_task(task_id, str(file_path))

        try:
            # 阶段 1：转换（内部会提前启动 VLM）
            vlm_task = await self._transform(state, output_dir)

            # 阶段 2：清洗 + 等待 VLM（并行）
            await self._clean_and_vlm(state, vlm_task)

            # 阶段 3：切分
            await self._chunk(state)

            # 阶段 4：Embedding + 索引（可选）
            if embedding_client and vector_index and keyword_index:
                await self._embed_and_index(state, embedding_client, vector_index, keyword_index)

            state.stage = PipelineStage.DONE
            state.completed_at = time.time()
            self._emit(state, "pipeline.completed", "预处理完成")

            if self._pipeline_monitor:
                self._pipeline_monitor.complete_task(task_id)

        except Exception as e:
            state.stage = PipelineStage.FAILED
            state.error = str(e)
            state.completed_at = time.time()
            self._emit(state, "pipeline.failed", f"预处理失败: {e}")
            logger.error("Pipeline 失败 [%s]: %s", task_id, e, exc_info=True)

            if self._pipeline_monitor:
                self._pipeline_monitor.fail_task(task_id, str(e))

        return state

    def get_state(self, task_id: str) -> PipelineState | None:
        return self._states.get(task_id)

    # ── 阶段实现 ──────────────────────────────────────────────

    async def _transform(self, state: PipelineState, output_dir: Path | None):
        """阶段 1：MinerU 转换，返回已启动的 VLM 任务"""
        state.stage = PipelineStage.TRANSFORMING
        self._emit(state, "transformation.started", "开始转换")

        def _on_mineru_progress(progress):
            self._emit(state, "transformation.mineru_progress", progress.message, {
                "state": progress.state.value,
                "extracted_pages": progress.extracted_pages,
                "total_pages": progress.total_pages,
            })

        from ..mineru_processing import convert_pdf
        result = await convert_pdf(
            state.file_path,
            output_dir=output_dir,
            on_mineru_progress=_on_mineru_progress,
        )

        if not result.success:
            raise RuntimeError(f"转换失败: {result.error}")

        state.results.conversion = result
        self._emit(state, "transformation.completed", "转换完成", {
            "char_count": len(result.markdown),
            "image_count": len(result.images),
        })

        # 关键优化：图片一到手就启动 VLM
        mineru_image_paths = result.mineru_metadata.get("image_paths", [])
        vlm_task = None
        has_vlm = bool(mineru_image_paths) or bool(result.images)
        if has_vlm:
            state.stage = PipelineStage.VLM_ENRICHING
            self._emit(state, "vlm.started", "VLM 理解已提前启动（与 transformation 剩余工作并行）")
            vlm_task = asyncio.create_task(self._run_vlm(result))

        return vlm_task

    async def _clean_and_vlm(self, state: PipelineState, vlm_task):
        """阶段 2：并行清洗 + VLM"""
        conversion_result = state.results.conversion
        if not conversion_result:
            return

        state.stage = PipelineStage.CLEANING
        self._emit(state, "cleaning.started", "开始清洗")
        cleaning_task = asyncio.create_task(self._run_cleaning(conversion_result))

        tasks_to_wait = [cleaning_task]
        if vlm_task is not None:
            tasks_to_wait.append(vlm_task)

        results = await asyncio.gather(*tasks_to_wait, return_exceptions=True)

        if not isinstance(results[0], Exception):
            state.results.cleaning = results[0]
        else:
            logger.warning("清洗失败: %s", results[0])
            self._emit(state, "pipeline.degraded", "清洗失败，使用原始 markdown")

        if vlm_task is not None:
            vlm_idx = 1
            if not isinstance(results[vlm_idx], Exception):
                state.results.vlm = results[vlm_idx]
            else:
                logger.warning("VLM 失败: %s", results[vlm_idx])
                self._emit(state, "pipeline.degraded", f"VLM 降级: {results[vlm_idx]}")

    async def _chunk(self, state: PipelineState):
        """阶段 3：语义切分"""
        state.stage = PipelineStage.CHUNKING
        self._emit(state, "chunking.started", "开始切分")

        conversion_result = state.results.conversion
        if not conversion_result:
            return

        cleaning_result = state.results.cleaning
        markdown = cleaning_result.markdown if cleaning_result else conversion_result.markdown

        vlm_result = state.results.vlm
        if vlm_result and vlm_result.analyses:
            from ..vlm_understanding import merge_vlm_into_markdown
            markdown = merge_vlm_into_markdown(markdown, vlm_result)

        state.results.final_markdown = markdown

        from ..chunking import semantic_chunk
        mineru_metadata = getattr(conversion_result, "mineru_metadata", {})
        chunks = semantic_chunk(markdown, source_file_path=str(state.file_path), mineru_metadata=mineru_metadata)
        state.results.chunks = chunks

        self._emit(state, "chunking.completed", f"切分完成，共 {len(chunks)} 个 chunk")

    async def _embed_and_index(
        self,
        state: PipelineState,
        embedding_client,
        vector_index,
        keyword_index,
    ):
        """阶段 4：Embedding + 索引（Chroma + BM25）"""
        chunks = state.results.chunks
        if not chunks:
            return

        paper_id = state.file_path.stem
        sm = self._storage_monitor

        # Embedding
        state.stage = PipelineStage.EMBEDDING
        self._emit(state, "embedding.started", f"开始 embedding，共 {len(chunks)} 个 chunk")

        texts = [c.content for c in chunks]
        try:
            t0 = time.perf_counter()
            vectors = await embedding_client.embed(texts)
            embed_ms = int((time.perf_counter() - t0) * 1000)
            state.results.vectors = vectors
            self._emit(state, "embedding.completed", f"embedding 完成，共 {len(vectors)} 个向量")
            if sm:
                sm.record_latency("embedding", embed_ms, chunk_count=len(chunks))
        except Exception as e:
            self._emit(state, "embedding.failed", f"embedding 失败: {e}")
            raise

        # Indexing
        state.stage = PipelineStage.INDEXING
        self._emit(state, "indexing.started", "开始索引")

        chunk_dicts = _build_chunk_dicts(chunks)
        inserted = vector_index.insert_chunks(paper_id, chunk_dicts, vectors)

        doc_ids = [f"{paper_id}_{i}" for i in range(len(chunks))]
        contents = [c.content for c in chunks]
        metadatas = [
            {
                "content": c.content,
                "paper_id": paper_id,
                "source_page": chunk_dicts[i].get("source_page", 0),
                "section_title": chunk_dicts[i].get("section_title", ""),
                "chunk_index": i,
                "parent_chunk_id": c.parent_chunk_id,
                "anchors": chunk_dicts[i].get("anchors", []),
            }
            for i, c in enumerate(chunks)
        ]
        keyword_index.add_documents(doc_ids, contents, metadatas=metadatas)

        self._emit(state, "indexing.completed", f"索引完成，Chroma: {inserted}，BM25: {len(doc_ids)}")

        if sm:
            try:
                chroma_count = vector_index._collection.count() if vector_index._collection else 0
                bm25_count = len(keyword_index._doc_ids) if hasattr(keyword_index, "_doc_ids") else 0
                sm.update_health(chroma_doc_count=chroma_count, bm25_doc_count=bm25_count)
            except Exception:
                pass

    # ── 内部工具 ──────────────────────────────────────────────

    async def _run_cleaning(self, conversion_result):
        from ..cleaning import clean_mineru_output
        metadata = getattr(conversion_result, "mineru_metadata", {})
        return clean_mineru_output(conversion_result.markdown, metadata=metadata)

    async def _run_vlm(self, conversion_result):
        from ..vlm_understanding import process_images
        mineru_metadata = getattr(conversion_result, "mineru_metadata", {})
        return await process_images(conversion_result.images, mineru_metadata=mineru_metadata)

    def _emit(self, state: PipelineState, event: str, message: str, data: dict = None):
        pipeline_event = PipelineEvent(
            event=event,
            stage=state.stage,
            task_id=state.task_id,
            message=message,
            data=data or {},
        )
        state.events.append(pipeline_event)

        if self._monitor_callback:
            self._monitor_callback(pipeline_event)

        logger.info("[%s] %s: %s", state.task_id, event, message)
        self._bridge_to_monitor(state, event, data or {})

    def _bridge_to_monitor(self, state: PipelineState, event: str, data: dict):
        monitor = self._pipeline_monitor
        if monitor is None:
            return

        task_id = state.task_id

        if event.endswith(".started") and not event.startswith("pipeline"):
            stage = event.rsplit(".", 1)[0]
            monitor.start_stage(task_id, stage)
        elif event.endswith(".completed") and not event.startswith("pipeline"):
            stage = event.rsplit(".", 1)[0]
            monitor.complete_stage(task_id, stage, details=data)
        elif event.endswith(".failed") and not event.startswith("pipeline"):
            stage = event.rsplit(".", 1)[0]
            monitor.fail_stage(task_id, stage, data.get("error", "unknown"))
        elif event == "pipeline.degraded":
            monitor.degrade_stage(task_id, state.stage.value, message=data.get("reason", "degraded"))


def _build_chunk_dicts(chunks: list) -> list[dict]:
    """将 chunk 对象转为字典（供 indexing 使用）"""
    chunk_dicts = []
    for c in chunks:
        anchor = c.anchors[0] if c.anchors else None
        chunk_dicts.append({
            "content": c.content,
            "chunk_type": c.chunk_type,
            "section_title": c.section_title,
            "has_image": str(c.has_image),
            "parent_chunk_id": c.parent_chunk_id,
            "source_page": anchor.page if anchor else 0,
            "file_hash": anchor.source_text_hash if anchor else "",
            "anchors": [
                {
                    "anchor_id": a.anchor_id,
                    "page": a.page,
                    "block_id": a.block_id,
                    "block_type": a.block_type,
                    "heading_path": a.heading_path,
                    "char_start": a.char_start,
                    "char_end": a.char_end,
                    "bbox": a.bbox,
                    "parent_anchor_id": a.parent_anchor_id,
                    "source_text_hash": a.source_text_hash,
                }
                for a in c.anchors
            ],
        })
    return chunk_dicts
