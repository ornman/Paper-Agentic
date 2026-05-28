"""预处理 Pipeline 调度器

类似 Scrapy 的 engine + scheduler 复合体。
负责整个预处理流程的编排。

关键优化：VLM 在 MinerU 返回图片的那一刻就开始异步执行，
与 transformation 的剩余工作（表单/表格提取）和 cleaning 并行。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger("paper-assistant")


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
class PipelineState:
    """Pipeline 状态"""
    task_id: str
    file_path: Path
    stage: PipelineStage = PipelineStage.QUEUED
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    events: list[PipelineEvent] = field(default_factory=list)


class PipelineOrchestrator:
    """Pipeline 编排器

    主循环轮询各阶段状态，调度整个预处理流程。

    时序优化：
    - VLM 在 MinerU 返回图片的那一刻就开始异步执行
    - cleaning 在 transformation 完成后立即开始
    - VLM 和 cleaning 并行，chunking 等两者都完成
    """

    def __init__(self, monitor_callback=None, *, embedding_client=None, vector_index=None, keyword_index=None):
        self._monitor_callback = monitor_callback
        self._states: dict[str, PipelineState] = {}
        self._embedding_client = embedding_client
        self._vector_index = vector_index
        self._keyword_index = keyword_index

    async def run(
        self,
        file_path: Path,
        output_dir: Path | None = None,
    ) -> PipelineState:
        """运行整个预处理 pipeline"""
        task_id = str(uuid.uuid4())[:8]
        state = PipelineState(task_id=task_id, file_path=file_path)
        self._states[task_id] = state

        try:
            # 阶段 1：转换（内部会提前启动 VLM）
            vlm_task = await self._run_transformation(state, output_dir)

            # 阶段 2：清洗 + 等待 VLM（并行）
            await self._run_cleaning_and_vlm(state, vlm_task)

            # 阶段 3：切分
            await self._run_chunking(state)

            # 阶段 4：Embedding + 索引（可选，需要外部依赖）
            if self._embedding_client and self._vector_index and self._keyword_index:
                await self._run_embedding_and_indexing(state)

            # 完成
            state.stage = PipelineStage.DONE
            state.completed_at = time.time()
            self._emit(state, "pipeline.completed", "预处理完成")

        except Exception as e:
            state.stage = PipelineStage.FAILED
            state.error = str(e)
            state.completed_at = time.time()
            self._emit(state, "pipeline.failed", f"预处理失败: {e}")
            logger.error("Pipeline 失败 [%s]: %s", task_id, e, exc_info=True)

        return state

    async def _run_transformation(self, state: PipelineState, output_dir: Path | None):
        """执行转换，返回已启动的 VLM 任务（如果有图片）

        时序：
        1. MinerU 解析 → 返回 markdown + images
        2. 立即启动 VLM 异步任务（不等待完成）
        3. 继续提取表单/表格（如有需要）
        4. 返回 VLM 任务给调用方
        """
        state.stage = PipelineStage.TRANSFORMING
        self._emit(state, "transformation.started", "开始转换")

        # MinerU 进度回调 → 转发为 pipeline 事件
        def _on_mineru_progress(progress):
            self._emit(state, "transformation.mineru_progress", progress.message, {
                "state": progress.state.value,
                "extracted_pages": progress.extracted_pages,
                "total_pages": progress.total_pages,
            })

        from ..transformation import convert_pdf
        result = await convert_pdf(
            state.file_path,
            output_dir=output_dir,
            on_mineru_progress=_on_mineru_progress,
        )

        if not result.success:
            raise RuntimeError(f"转换失败: {result.error}")

        state._conversion_result = result
        self._emit(state, "transformation.completed", "转换完成", {
            "char_count": len(result.markdown),
            "image_count": len(result.images),
        })

        # ── 关键优化：图片一到手就启动 VLM ──
        # 只要 MinerU metadata 里有 image_paths，或有图片，就触发 VLM
        mineru_image_paths = result.mineru_metadata.get("image_paths", [])
        vlm_task = None
        has_vlm = bool(mineru_image_paths) or bool(result.images)
        if has_vlm:
            state.stage = PipelineStage.VLM_ENRICHING
            self._emit(state, "vlm.started", "VLM 理解已提前启动（与 transformation 剩余工作并行）")
            vlm_task = asyncio.create_task(self._run_vlm(result))

        return vlm_task

    async def _run_cleaning_and_vlm(self, state: PipelineState, vlm_task):
        """并行执行清洗，等待 VLM 完成

        VLM 已在 transformation 阶段提前启动，这里只需等待结果。
        Cleaning 在此时启动，与 VLM 并行。
        """
        conversion_result = getattr(state, "_conversion_result", None)
        if not conversion_result:
            return

        # 启动清洗
        state.stage = PipelineStage.CLEANING
        self._emit(state, "cleaning.started", "开始清洗")
        cleaning_task = asyncio.create_task(self._run_cleaning(conversion_result))

        # 等待 cleaning 和 VLM 都完成
        tasks_to_wait = [cleaning_task]
        task_labels = ["cleaning"]

        if vlm_task is not None:
            tasks_to_wait.append(vlm_task)
            task_labels.append("vlm")

        results = await asyncio.gather(*tasks_to_wait, return_exceptions=True)

        # 保存 cleaning 结果
        if not isinstance(results[0], Exception):
            state._cleaning_result = results[0]
        else:
            logger.warning("清洗失败: %s", results[0])
            self._emit(state, "pipeline.degraded", "清洗失败，使用原始 markdown")

        # 保存 VLM 结果
        if vlm_task is not None:
            vlm_idx = 1
            if not isinstance(results[vlm_idx], Exception):
                state._vlm_result = results[vlm_idx]
            else:
                logger.warning("VLM 失败: %s", results[vlm_idx])
                self._emit(state, "pipeline.degraded", f"VLM 降级: {results[vlm_idx]}")

    async def _run_cleaning(self, conversion_result):
        """执行 MinerU 专用清洗"""
        from ..cleaning import clean_mineru_output
        metadata = getattr(conversion_result, "mineru_metadata", {})
        return clean_mineru_output(conversion_result.markdown, metadata=metadata)

    async def _run_vlm(self, conversion_result):
        """执行 VLM 理解"""
        from ..vlm_understanding import process_images
        mineru_metadata = getattr(conversion_result, "mineru_metadata", {})
        return await process_images(conversion_result.images, mineru_metadata=mineru_metadata)

    async def _run_chunking(self, state: PipelineState):
        """执行切分"""
        state.stage = PipelineStage.CHUNKING
        self._emit(state, "chunking.started", "开始切分")

        conversion_result = getattr(state, "_conversion_result", None)
        if not conversion_result:
            return

        # 优先使用清洗后的 markdown
        cleaning_result = getattr(state, "_cleaning_result", None)
        markdown = cleaning_result.markdown if cleaning_result else conversion_result.markdown

        # 如果有 VLM 结果，回填到 markdown
        vlm_result = getattr(state, "_vlm_result", None)
        if vlm_result and vlm_result.analyses:
            from ..vlm_understanding import merge_vlm_into_markdown
            markdown = merge_vlm_into_markdown(markdown, vlm_result)

        state._final_markdown = markdown

        from ..chunking import semantic_chunk
        mineru_metadata = getattr(conversion_result, "mineru_metadata", {})
        chunks = semantic_chunk(markdown, source_file_path=str(state.file_path), mineru_metadata=mineru_metadata)
        state._chunks = chunks

        self._emit(state, "chunking.completed", f"切分完成，共 {len(chunks)} 个 chunk")

    def _emit(self, state: PipelineState, event: str, message: str, data: dict = None):
        """发送事件"""
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

    async def _run_embedding_and_indexing(self, state: PipelineState):
        """执行 embedding + 索引（Chroma + BM25）"""
        chunks = getattr(state, "_chunks", None)
        if not chunks:
            return

        paper_id = state.file_path.stem

        # Embedding
        state.stage = PipelineStage.EMBEDDING
        self._emit(state, "embedding.started", f"开始 embedding，共 {len(chunks)} 个 chunk")

        texts = [c.content for c in chunks]
        try:
            vectors = await self._embedding_client.embed(texts)
            state._vectors = vectors
            self._emit(state, "embedding.completed", f"embedding 完成，共 {len(vectors)} 个向量")
        except Exception as e:
            self._emit(state, "embedding.failed", f"embedding 失败: {e}")
            raise

        # Indexing
        state.stage = PipelineStage.INDEXING
        self._emit(state, "indexing.started", "开始索引")

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

        inserted = self._vector_index.insert_chunks(paper_id, chunk_dicts, vectors)
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
        self._keyword_index.add_documents(doc_ids, contents, metadatas=metadatas)

        self._emit(state, "indexing.completed", f"索引完成，Chroma: {inserted}，BM25: {len(doc_ids)}")

    def get_state(self, task_id: str) -> PipelineState | None:
        """获取 pipeline 状态"""
        return self._states.get(task_id)
