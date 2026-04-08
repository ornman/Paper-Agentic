# 索引服务
# Task 5 只实现最小双索引写入能力：
# 1. 根据 index_mode 选择 brute / parent_child 切块
# 2. 在写入前校验 embedding 模型与维度契约
# 3. 同时写入 Chroma 与 BM25
# 4. 支持按 document_id 同步删除
# 5. 支持 parent_child 的子块回挂父块

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.core.config import PINNED_EMBEDDING_DIMENSIONS, PINNED_EMBEDDING_MODEL
from app.core.errors import IndexingError
from app.modules.ingestion.dto import CleanedDocument
from app.modules.indexing.bm25_repo import BM25Repo
from app.modules.indexing.chroma_repo import ChromaRepo
from app.modules.indexing.chunkers.brute import build_brute_index
from app.modules.indexing.chunkers.parent_child import build_parent_child_index
from app.modules.indexing.dto import DeleteIndexResult, IndexWriteResult, IndexedChunk


@runtime_checkable
class EmbeddingClientProtocol(Protocol):
    """索引服务依赖的最小 embedding 契约。"""

    model_name: str
    dimensions: int

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量返回向量。"""


class IndexingService:
    """双索引写入服务。"""

    def __init__(
        self,
        *,
        embedding_client: EmbeddingClientProtocol | None = None,
        chroma_repo: ChromaRepo | None = None,
        bm25_repo: BM25Repo | None = None,
    ) -> None:
        if embedding_client is None:
            from app.clients.embedding_client import EmbeddingClient

            embedding_client = EmbeddingClient()

        self.embedding_client = embedding_client
        self.chroma_repo = chroma_repo or ChromaRepo()
        self.bm25_repo = bm25_repo or BM25Repo()

    async def index_document(self, cleaned_document: CleanedDocument) -> IndexWriteResult:
        """把清洗后的文档写入双索引。"""
        self._validate_embedding_contract()

        all_bm25_chunks, vector_chunks = self._build_chunks(cleaned_document)
        if not all_bm25_chunks:
            raise IndexingError(
                code="index_chunks_empty",
                message="索引构建失败：没有可写入的块",
                detail={"document_id": cleaned_document.document_id},
            )

        # 这里必须先把“新数据是否可写”验证完，再动旧索引。
        # 根因是上一版在 embedding 还没成功前就先 delete_document()，
        # 一旦 embed 或维度校验报错，旧索引就已经被提前删空了。
        vector_embeddings = await self.embedding_client.embed([chunk.text for chunk in vector_chunks])
        self._validate_embedding_output(vector_chunks, vector_embeddings)

        document_id = cleaned_document.document_id

        # 先抓旧快照，再做替换。
        # 本质原因是 Chroma/BM25 不共享事务，跨仓储“重建”只能靠应用层补偿。
        # 如果不提前抓旧状态，一旦删旧成功、新写失败，就没有恢复锚点。
        previous_chroma_snapshot = self.chroma_repo.snapshot_document(document_id=document_id)
        previous_bm25_snapshot = self.bm25_repo.snapshot()

        try:
            self._delete_document_indexes(document_id)

            vector_count = self.chroma_repo.upsert_chunks(vector_chunks, vector_embeddings)
            self.bm25_repo.upsert_chunks(all_bm25_chunks)
        except Exception:
            self._restore_previous_indexes(
                document_id=document_id,
                previous_chroma_snapshot=previous_chroma_snapshot,
                previous_bm25_snapshot=previous_bm25_snapshot,
            )
            raise

        searchable_bm25_count = sum(1 for chunk in all_bm25_chunks if chunk.searchable)
        return IndexWriteResult(
            document_id=cleaned_document.document_id,
            index_mode=cleaned_document.index_mode,
            vector_count=vector_count,
            bm25_count=searchable_bm25_count,
        )

    def attach_parent_context(self, chunk_ids: list[str]) -> list[IndexedChunk]:
        """把命中的子块回挂到父块。

        规则：
        - child -> 返回其 parent
        - brute / parent -> 直接返回自己
        - 去重并保持输入顺序
        """
        if not chunk_ids:
            return []

        chunks = self.bm25_repo.get_chunks_by_ids(chunk_ids)
        if not chunks:
            return []

        all_chunks = self.bm25_repo.get_chunks_by_ids([chunk.chunk_id for chunk in self.bm25_repo._all_chunks])
        chunk_map = {chunk.chunk_id: chunk for chunk in all_chunks}

        attached_chunks: list[IndexedChunk] = []
        seen_chunk_ids: set[str] = set()

        for chunk in chunks:
            target_chunk = chunk
            if chunk.node_kind == "child" and chunk.parent_chunk_id:
                target_chunk = chunk_map.get(chunk.parent_chunk_id, chunk)
            if target_chunk.chunk_id in seen_chunk_ids:
                continue
            attached_chunks.append(target_chunk)
            seen_chunk_ids.add(target_chunk.chunk_id)

        return attached_chunks

    def delete_document(self, document_id: str) -> DeleteIndexResult:
        """同步删除单个文档的全部索引。

        这里必须做应用层补偿，原因是：
        1. Chroma 与 BM25 没有共享事务
        2. 删除顺序是先 Chroma、再 BM25
        3. 一旦 BM25 删除或保存失败，Chroma 可能已经先被删掉

        所以删除前先抓旧快照，失败后把两个仓储都恢复回旧状态，
        避免出现“向量没了、BM25 还在”或反过来的半删除状态。
        """
        previous_chroma_snapshot = self.chroma_repo.snapshot_document(document_id=document_id)
        previous_bm25_snapshot = self.bm25_repo.snapshot()

        try:
            return self._delete_document_indexes(document_id)
        except Exception:
            self._restore_previous_indexes(
                document_id=document_id,
                previous_chroma_snapshot=previous_chroma_snapshot,
                previous_bm25_snapshot=previous_bm25_snapshot,
            )
            raise

    def _delete_document_indexes(self, document_id: str) -> DeleteIndexResult:
        """执行不带补偿的底层双索引删除。

        这个私有方法只负责真正删数据，
        是否做快照与回滚由调用方决定：
        - 公共 delete_document() 自己负责补偿
        - index_document() 用自己的大事务补偿包住它
        """
        deleted_vector_count = self.chroma_repo.delete_document(document_id)
        deleted_bm25_count = self.bm25_repo.delete_document(document_id)
        return DeleteIndexResult(
            document_id=document_id,
            deleted_vector_count=deleted_vector_count,
            deleted_bm25_count=deleted_bm25_count,
        )

    def _restore_previous_indexes(
        self,
        *,
        document_id: str,
        previous_chroma_snapshot: list[dict[str, object]],
        previous_bm25_snapshot: list[IndexedChunk],
    ) -> None:
        """在双索引替换失败时恢复旧状态。

        这里的目标不是实现一个复杂事务框架，
        而是给 Task 5 补上最小闭环：
        1. 先删掉当前文档可能已经写进去的新 Chroma 数据
        2. 再把旧的 Chroma 快照恢复回去
        3. 只在 BM25 当前状态已经偏离旧快照时，再恢复 BM25

        这样即使失败发生在“删旧之后、写新过程中”，
        旧索引也仍然有机会回到一致状态。
        """
        self.chroma_repo.delete_document(document_id)
        if previous_chroma_snapshot:
            self.chroma_repo.restore_document(previous_chroma_snapshot)

        current_bm25_snapshot = self.bm25_repo.snapshot()
        if current_bm25_snapshot != previous_bm25_snapshot:
            self.bm25_repo.restore(previous_bm25_snapshot)

    def _build_chunks(self, cleaned_document: CleanedDocument) -> tuple[list[IndexedChunk], list[IndexedChunk]]:
        """根据 index_mode 构造 BM25 / Chroma 要写入的块。"""
        if cleaned_document.index_mode == "brute":
            brute_result = build_brute_index(cleaned_document)
            return brute_result.chunks, brute_result.chunks

        if cleaned_document.index_mode == "parent_child":
            parent_child_result = build_parent_child_index(cleaned_document)
            return (
                [*parent_child_result.parent_blocks, *parent_child_result.child_chunks],
                parent_child_result.child_chunks,
            )

        raise IndexingError(
            code="unsupported_index_mode",
            message=f"不支持的索引模式: {cleaned_document.index_mode}",
            detail={"document_id": cleaned_document.document_id},
        )

    def _validate_embedding_contract(self) -> None:
        """在写入前强制验证 embedding 契约。"""
        model_name = getattr(self.embedding_client, "model_name", None)
        dimensions = getattr(self.embedding_client, "dimensions", None)

        if model_name != PINNED_EMBEDDING_MODEL:
            raise IndexingError(
                code="embedding_model_mismatch",
                message=f"Embedding 模型必须固定为 {PINNED_EMBEDDING_MODEL}",
                detail={"actual_model": model_name},
            )
        if dimensions != PINNED_EMBEDDING_DIMENSIONS:
            raise IndexingError(
                code="embedding_dimensions_mismatch",
                message=f"Embedding 维度必须固定为 {PINNED_EMBEDDING_DIMENSIONS}",
                detail={"actual_dimensions": dimensions},
            )

    def _validate_embedding_output(
        self,
        vector_chunks: list[IndexedChunk],
        vector_embeddings: list[list[float]],
    ) -> None:
        """校验 embedding 输出数量与维度，防止脏数据写入向量库。"""
        if len(vector_chunks) != len(vector_embeddings):
            raise IndexingError(
                code="embedding_output_count_mismatch",
                message="Embedding 返回数量与待写入块数量不一致",
                detail={
                    "chunk_count": len(vector_chunks),
                    "embedding_count": len(vector_embeddings),
                },
            )

        for index, embedding in enumerate(vector_embeddings):
            if len(embedding) != PINNED_EMBEDDING_DIMENSIONS:
                raise IndexingError(
                    code="embedding_output_dimensions_mismatch",
                    message=f"Embedding 返回向量维度必须为 {PINNED_EMBEDDING_DIMENSIONS}",
                    detail={
                        "chunk_id": vector_chunks[index].chunk_id,
                        "actual_dimensions": len(embedding),
                    },
                )
