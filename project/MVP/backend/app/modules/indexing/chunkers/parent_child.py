# parent_child 切块器
# 目标：
# 1. 先构造较大的父块，作为最终展示与引用上下文
# 2. 再在每个父块内部构造较小的子块，作为检索入口
# 3. 当子块被召回时，能够稳定回挂到所属父块

from __future__ import annotations

from app.modules.ingestion.dto import CleanedDocument
from app.modules.indexing.chunkers.brute import (
    build_chunk_from_token_window,
    flatten_blocks,
    iter_token_windows,
)
from app.modules.indexing.dto import IndexedChunk, ParentChildIndexBuildResult

# 当前取值遵循“父块更大、子块更小”的最小实现思路：
# - 父块 900 token，100 token 重叠
# - 子块 500 token，50 token 重叠
# 这样仍然满足“子块比父块更聚焦”，同时复用当前稳定窗口逻辑。
DEFAULT_PARENT_CHUNK_SIZE = 900
DEFAULT_PARENT_OVERLAP = 100
DEFAULT_CHILD_CHUNK_SIZE = 500
DEFAULT_CHILD_OVERLAP = 50


def build_parent_child_index(
    cleaned_document: CleanedDocument,
    *,
    parent_chunk_size: int = DEFAULT_PARENT_CHUNK_SIZE,
    parent_overlap: int = DEFAULT_PARENT_OVERLAP,
    child_chunk_size: int = DEFAULT_CHILD_CHUNK_SIZE,
    child_overlap: int = DEFAULT_CHILD_OVERLAP,
) -> ParentChildIndexBuildResult:
    """构建 parent_child 模式索引块。"""
    flattened_tokens = flatten_blocks(cleaned_document.blocks)
    parent_windows = iter_token_windows(
        flattened_tokens,
        chunk_size=parent_chunk_size,
        overlap=parent_overlap,
    )

    parent_blocks: list[IndexedChunk] = []
    child_chunks: list[IndexedChunk] = []

    for parent_index, parent_window in enumerate(parent_windows):
        parent_chunk_id = f"{cleaned_document.document_id}::parent::{parent_index:04d}"
        parent_block = build_chunk_from_token_window(
            document_id=cleaned_document.document_id,
            chunk_id=parent_chunk_id,
            token_window=parent_window,
            node_kind="parent",
            searchable=False,
        )
        parent_blocks.append(parent_block)

        child_windows = iter_token_windows(
            parent_window,
            chunk_size=child_chunk_size,
            overlap=child_overlap,
        )
        for child_index, child_window in enumerate(child_windows):
            child_chunks.append(
                build_chunk_from_token_window(
                    document_id=cleaned_document.document_id,
                    chunk_id=(
                        f"{cleaned_document.document_id}::child::"
                        f"{parent_index:04d}::{child_index:04d}"
                    ),
                    token_window=child_window,
                    node_kind="child",
                    searchable=True,
                    parent_chunk_id=parent_chunk_id,
                )
            )

    return ParentChildIndexBuildResult(
        parent_blocks=parent_blocks,
        child_chunks=child_chunks,
    )


def attach_parent_blocks(
    result: ParentChildIndexBuildResult,
    child_chunk_ids: list[str],
) -> list[IndexedChunk]:
    """把命中的子块回挂到父块。

    返回去重后的父块列表，保持 child_chunk_ids 的出现顺序。
    """
    if not child_chunk_ids:
        return []

    child_map = {child.chunk_id: child for child in result.child_chunks}
    parent_map = {parent.chunk_id: parent for parent in result.parent_blocks}

    attached_parents: list[IndexedChunk] = []
    seen_parent_ids: set[str] = set()

    for child_chunk_id in child_chunk_ids:
        child_chunk = child_map.get(child_chunk_id)
        if child_chunk is None or child_chunk.parent_chunk_id is None:
            continue
        if child_chunk.parent_chunk_id in seen_parent_ids:
            continue
        parent_chunk = parent_map.get(child_chunk.parent_chunk_id)
        if parent_chunk is None:
            continue
        attached_parents.append(parent_chunk)
        seen_parent_ids.add(parent_chunk.chunk_id)

    return attached_parents
