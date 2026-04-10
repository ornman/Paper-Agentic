# 导入服务编排（完整版）
# 完整流程：MinerU 解析 → 清洗 → VLM 图片描述 → 混合切分 → Embedding → Qdrant 存储

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from app.clients.embedding_client import EmbeddingClient
from app.clients.kimi_client import KimiVLMClient
from app.clients.vlm_client import VLMClient
from app.core.config import get_settings
from app.core.errors import IngestionError
from app.core.retry import retry_async
from app.models.base import Chunk
from app.modules.ingestion.cleaning import clean_mineru_payload
from app.modules.ingestion.dto import CleanedDocument
from app.modules.ingestion.mineru_client import MineruClient
from app.modules.library.models import DocumentRecord
from app.modules.library.repository import LibraryRepository
from app.processing.chunker import SemanticChunk, chunk_by_semantic_units
from app.processing.describer import describe_chunks_async
from app.stores.qdrant_store import QdrantStore

settings = get_settings()

# Task 4 当前能接受的 MinerU 最小成功载荷结构。
_MINERU_MINIMAL_SUCCESS_KEYS = {"pages"}


class IngestionService:
    """完整导入编排服务."""

    def __init__(
        self,
        *,
        repository: Optional[LibraryRepository] = None,
        mineru_client: Optional[MineruClient] = None,
        vlm_client: Optional[VLMClient] = None,
        embedding_client: Optional[EmbeddingClient] = None,
        qdrant_store: Optional[QdrantStore] = None,
    ) -> None:
        self.repository = repository or LibraryRepository()
        self.mineru_client = mineru_client or MineruClient()
        self.vlm_client = vlm_client or KimiVLMClient()
        self.embedding_client = embedding_client or EmbeddingClient()
        self.qdrant_store = qdrant_store or QdrantStore()

    def ingest_document(self, record: DocumentRecord) -> DocumentRecord:
        """执行文档导入链路，并返回最终文档状态（完整版）."""
        current_record = self.repository.save_document(record.transition("parsing"))

        try:
            # 阶段1: MinerU 解析
            print(f"[INGEST] 阶段1: MinerU 解析...")
            mineru_payload = self.mineru_client.run_pdf_task(current_record.file_path)
            self._validate_success_payload_shape(mineru_payload)
            print(f"[INGEST]   ✅ 解析完成")

            current_record = self.repository.save_document(current_record.transition("cleaning"))

            # 阶段2: 清洗
            print(f"[INGEST] 阶段2: 清洗数据...")
            cleaned_document = self._clean_document(current_record, mineru_payload)
            if cleaned_document.cleaned_block_count == 0:
                raise IngestionError(
                    code="cleaned_document_empty",
                    message="清洗后无有效正文块，导入失败",
                    detail={"document_id": current_record.document_id},
                )
            print(f"[INGEST]   ✅ 清洗完成: {cleaned_document.cleaned_block_count} blocks")

            # 阶段3: VLM 图片描述
            image_count = self._count_images(mineru_payload)
            if image_count > 0:
                print(f"[INGEST] 阶段3: VLM 图片描述 ({image_count} images)...")
                chunks_with_images = asyncio.run(self._describe_images(
                    current_record,
                    mineru_payload,
                ))
                print(f"[INGEST]   ✅ 描述完成")
            else:
                print(f"[INGEST] 阶段3: VLM 图片描述 (跳过，无图片)")
                chunks_with_images = self._blocks_to_chunks(current_record, cleaned_document)

            # 阶段4: 混合切分
            print(f"[INGEST] 阶段4: 混合切分...")
            text_chunks = self._chunk_chunks(current_record, chunks_with_images)
            print(f"[INGEST]   ✅ 切分完成: {len(text_chunks)} text chunks")

            current_record = self.repository.save_document(current_record.transition("indexing"))

            # 阶段5: Embedding
            print(f"[INGEST] 阶段5: Embedding ({len(text_chunks)} chunks)...")
            embeddings = asyncio.run(self._embed_chunks(text_chunks))
            print(f"[INGEST]   ✅ Embedding 完成: {len(embeddings)} vectors")

            # 阶段6: Qdrant 存储
            print(f"[INGEST] 阶段6: Qdrant 存储...")
            final_chunks = self._convert_to_final_chunks(current_record.document_id, text_chunks)
            self.qdrant_store.add_chunks(current_record.document_id, final_chunks, embeddings)
            print(f"[INGEST]   ✅ 存储完成")

            completed_record = current_record.transition("completed").model_copy(
                update={
                    "error_stage": None,
                    "error_message": None,
                }
            )
            return self.repository.save_document(completed_record)

        except IngestionError as exc:
            return self._mark_failed(current_record, exc)
        except Exception as exc:  # noqa: BLE001
            unexpected_error = IngestionError(
                code="ingestion_failed",
                message=f"导入链路执行失败: {exc}",
                detail={"document_id": current_record.document_id},
            )
            return self._mark_failed(current_record, unexpected_error)

    def _clean_document(self, record: DocumentRecord, mineru_payload: dict) -> CleanedDocument:
        """调用清洗入口，把 MinerU 结果归一化为正文块."""
        return clean_mineru_payload(
            document_id=record.document_id,
            title=record.title,
            file_path=record.file_path,
            index_mode=record.index_mode,
            payload=mineru_payload,
        )

    def _count_images(self, mineru_payload: dict) -> int:
        """统计 MinerU 结果中的图片数量."""
        pages = mineru_payload.get("pages", [])
        image_count = 0
        for page_item in pages:
            if not isinstance(page_item, dict):
                continue
            blocks = page_item.get("blocks", [])
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                # 检查是否为图片块
                block_type = block.get("type", "")
                if block_type in ("image", "figure", "picture"):
                    image_count += 1
        return image_count

    def _blocks_to_chunks(
        self,
        record: DocumentRecord,
        cleaned_document: CleanedDocument,
    ) -> list[Chunk]:
        """将清洗后的块转换为 Chunk 格式（支持文本和图片）."""
        chunks = []
        for block in cleaned_document.blocks:
            chunks.append(
                Chunk(
                    id=block.block_id,
                    paper=record.document_id,
                    chunk_type=block.block_type,  # 使用实际的 block_type
                    content=block.content,  # 使用 content 字段
                    section="",
                    page=block.page,
                    image_path=block.image_path,  # 保留图片路径
                    metadata=block.metadata,
                )
            )
        return chunks

    @retry_async(max_retries=3)
    async def _describe_images(
        self,
        record: DocumentRecord,
        mineru_payload: dict,
    ) -> list[Chunk]:
        """为图片生成 VLM 描述（带重试）."""
        # 先构建基础 chunks
        chunks = self._mineru_to_chunks(record, mineru_payload)

        # 过滤出有图片的 chunks
        paper_dir = Path(record.file_path).parent
        image_chunks = [c for c in chunks if c.image_path]

        if not image_chunks:
            return chunks

        # 并发调用 VLM
        described_chunks = await describe_chunks_async(paper_dir, chunks, self.vlm_client)

        return described_chunks

    def _mineru_to_chunks(
        self,
        record: DocumentRecord,
        mineru_payload: dict,
    ) -> list[Chunk]:
        """将 MinerU payload 转换为 Chunk 列表."""
        chunks = []
        pages = mineru_payload.get("pages", [])

        for page_item in pages:
            if not isinstance(page_item, dict):
                continue
            page_number = page_item.get("page", 0)
            blocks = page_item.get("blocks", [])

            for block_index, block in enumerate(blocks):
                if not isinstance(block, dict):
                    continue

                # 提取文本
                text = ""
                for field_name in ("text", "content", "markdown", "md"):
                    value = block.get(field_name)
                    if isinstance(value, str):
                        text = value
                        break

                if not text:
                    continue

                # 检查是否为图片块
                block_type = block.get("type", "")
                image_path = None
                if block_type in ("image", "figure", "picture"):
                    # 尝试提取图片路径
                    image_path = block.get("image_path") or block.get("path")

                chunks.append(
                    Chunk(
                        id=f"{record.document_id}_p{page_number}_b{block_index}",
                        paper=record.document_id,
                        chunk_type="image" if image_path else "text",
                        content=text,
                        section="",
                        page=page_number,
                        image_path=image_path,
                        metadata={"raw_block_type": block_type},
                    )
                )

        return chunks

    def _chunk_chunks(self, record: DocumentRecord, chunks: list[Chunk]) -> list[dict]:
        """对 chunks 进行混合语义切分."""
        # 转换为 SemanticChunk
        semantic_chunks = [
            SemanticChunk(
                content=c.content,
                section=c.section,
                metadata={"chunk_type": c.chunk_type, "image_path": c.image_path},
            )
            for c in chunks
        ]

        # 执行切分
        text_chunks = chunk_by_semantic_units(semantic_chunks)

        # 转换为字典格式
        result = []
        for i, tc in enumerate(text_chunks):
            result.append({
                "content": tc.content,
                "section": tc.section,
                "page": tc.metadata.get("page", 0),
                "chunk_type": tc.metadata.get("chunk_type", "text"),
                "image_path": tc.metadata.get("image_path"),
                "metadata": tc.metadata,
            })

        return result

    @retry_async(max_retries=3)
    async def _embed_chunks(self, chunks: list[dict]) -> list[list[float]]:
        """为 chunks 生成 Embedding（带重试）."""
        texts = [c["content"] for c in chunks]
        return await self.embedding_client.embed(texts)

    def _convert_to_final_chunks(
        self,
        paper_id: str,
        chunks: list[dict],
    ) -> list[Chunk]:
        """转换为最终的 Chunk 格式."""
        final_chunks = []
        for i, c in enumerate(chunks):
            final_chunks.append(
                Chunk(
                    id=f"{paper_id}_chunk{i:04d}",
                    paper=paper_id,
                    chunk_type=c.get("chunk_type", "text"),
                    content=c["content"],
                    section=c["section"],
                    page=c.get("page", 0),
                    image_path=c.get("image_path"),
                    metadata=c.get("metadata", {}),
                )
            )
        return final_chunks

    def _validate_success_payload_shape(self, mineru_payload: dict) -> None:
        """校验成功态 payload 的最小结构."""
        if not isinstance(mineru_payload, dict):
            raise IngestionError(
                code="mineru_invalid_response",
                message="MinerU 成功结果不是 JSON 对象",
                detail={"payload_type": type(mineru_payload).__name__},
            )
        if not _MINERU_MINIMAL_SUCCESS_KEYS.issubset(mineru_payload.keys()):
            raise IngestionError(
                code="mineru_invalid_response",
                message="MinerU 成功结果缺少最小正文结构字段",
                detail={"required_keys": sorted(_MINERU_MINIMAL_SUCCESS_KEYS)},
            )

        pages = mineru_payload.get("pages")
        if not isinstance(pages, list):
            raise IngestionError(
                code="mineru_invalid_response",
                message="pages 必须是数组",
                detail={"pages_type": type(pages).__name__},
            )

        for page_index, page_item in enumerate(pages):
            if not isinstance(page_item, dict):
                raise IngestionError(
                    code="mineru_invalid_response",
                    message=f"pages[{page_index}] 必须是对象",
                    detail={"page_item_type": type(page_item).__name__},
                )

    def _mark_failed(self, record: DocumentRecord, error: IngestionError) -> DocumentRecord:
        """把当前记录推进到 failed，并写入统一错误信息."""
        failed_record = record.transition("failed").model_copy(
            update={
                "error_stage": error.stage,
                "error_message": error.message,
            }
        )
        return self.repository.save_document(failed_record)
