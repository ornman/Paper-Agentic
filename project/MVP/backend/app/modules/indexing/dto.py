# 索引模块 DTO
# 这里统一定义 Task 5 的最小数据契约：
# 1. 切块产物
# 2. parent_child 的父子结构
# 3. 索引写入 / 删除结果
# 4. BM25 查询命中结果

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class IndexedChunk(BaseModel):
    """统一的索引块结构。

    设计原因：
    1. brute 和 parent_child 最终都要落到同一套索引仓储。
    2. 统一字段后，service 层只需要关心“写什么”，不需要区分具体 chunker 的内部结构。
    3. 保留 parent_chunk_id，才能支持“子召回后回挂父”。
    """

    chunk_id: str
    document_id: str
    text: str
    page_start: int
    page_end: int
    source_block_ids: list[str] = Field(default_factory=list)
    node_kind: Literal["brute", "parent", "child"]
    searchable: bool = True
    parent_chunk_id: Optional[str] = None

    model_config = {"frozen": True}


class BruteIndexBuildResult(BaseModel):
    """brute 模式的切块结果。"""

    mode: Literal["brute"] = "brute"
    chunks: list[IndexedChunk] = Field(default_factory=list)

    model_config = {"frozen": True}


class ParentChildIndexBuildResult(BaseModel):
    """parent_child 模式的切块结果。"""

    mode: Literal["parent_child"] = "parent_child"
    parent_blocks: list[IndexedChunk] = Field(default_factory=list)
    child_chunks: list[IndexedChunk] = Field(default_factory=list)

    model_config = {"frozen": True}


class IndexWriteResult(BaseModel):
    """索引写入结果。"""

    document_id: str
    index_mode: str
    vector_count: int
    bm25_count: int

    model_config = {"frozen": True}


class DeleteIndexResult(BaseModel):
    """索引删除结果。"""

    document_id: str
    deleted_vector_count: int
    deleted_bm25_count: int

    model_config = {"frozen": True}


class BM25SearchHit(BaseModel):
    """BM25 命中结果。

    这里直接把块的核心定位信息带出来，
    是为了让后续 retrieval 模块可以直接复用，
    但当前 Task 5 只用到 chunk_id / parent_chunk_id / score / text。
    """

    chunk_id: str
    document_id: str
    text: str
    score: float
    node_kind: Literal["brute", "parent", "child"]
    searchable: bool
    parent_chunk_id: Optional[str] = None
    page_start: int = 0
    page_end: int = 0

    model_config = {"frozen": True}
