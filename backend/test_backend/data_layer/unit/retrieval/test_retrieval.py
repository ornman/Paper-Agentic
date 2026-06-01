"""Retrieval 模块测试

RET-U01: Dense score 传递
RET-U02: Sparse 返回类型
RET-U03: RRF 融合完整性
"""

from __future__ import annotations

import pytest
import tempfile
from pathlib import Path

from app.data_layer.retrieval.dense.vector_retriever import DenseRetriever, RetrievalDoc
from app.data_layer.retrieval.sparse.keyword_retriever import SparseRetriever, SparseResult
from app.data_layer.retrieval.fusion.rrf_fusion import rrf_fuse, FusedDoc
from app.data_layer.indexing.chroma_store.vector_index import VectorIndex, Doc
from app.data_layer.indexing.chroma_store.keyword_index import KeywordIndex


class TestRETU01:
    """Dense score 传递"""

    def test_dense_retriever_passes_score(self, tmp_dir):
        """DenseRetriever 正确传递 score"""
        index = VectorIndex(path=str(tmp_dir / "chroma"), dimension=128)
        index.init()

        chunks = [{"content": "测试文本", "chunk_type": "p"}]
        vectors = [[1.0] * 128]
        index.insert_chunks("p1", chunks, vectors)

        retriever = DenseRetriever(index)
        results = retriever.retrieve(query_vector=[1.0] * 128, topk=1)

        assert len(results) == 1
        assert results[0].score > 0  # 之前默认为 0
        assert results[0].id == "p1_0"

        index.close()

    def test_retrieval_doc_dataclass(self):
        """RetrievalDoc 数据结构"""
        doc = RetrievalDoc(id="test", content="text", score=0.95)
        assert doc.id == "test"
        assert doc.score == 0.95


class TestRETU02:
    """Sparse 返回类型"""

    def test_sparse_result_dataclass(self):
        """SparseResult 数据结构"""
        result = SparseResult(doc_id="doc1", score=1.5)
        assert result.doc_id == "doc1"
        assert result.score == 1.5

    def test_sparse_retriever_returns_sparse_result(self, tmp_dir):
        """SparseRetriever 返回 SparseResult 列表"""
        index = KeywordIndex(index_dir=str(tmp_dir / "bm25"))
        index.init()
        index.add_documents(["doc1_0"], ["深度学习研究"])

        retriever = SparseRetriever(index)
        results = retriever.retrieve("深度学习", topk=5)

        assert len(results) >= 1
        assert all(isinstance(r, SparseResult) for r in results)
        assert results[0].doc_id == "doc1_0"


class TestRETU03:
    """RRF 融合完整性"""

    def test_rrf_fuse_dense_only(self):
        """只有 dense 结果时正常工作"""
        dense = [
            Doc(id="d1", fields={"content": "text1"}),
            Doc(id="d2", fields={"content": "text2"}),
        ]
        results = rrf_fuse(dense_results=dense, sparse_results=[], topk=5)
        assert len(results) == 2
        assert all(isinstance(r, FusedDoc) for r in results)

    def test_rrf_fuse_sparse_only(self):
        """只有 sparse 结果时正常工作"""
        sparse = [SparseResult(doc_id="s1", score=1.0)]
        results = rrf_fuse(dense_results=[], sparse_results=sparse, topk=5)
        assert len(results) == 1
        assert results[0].id == "s1"

    def test_rrf_fuse_union_not_intersection(self):
        """融合是并集而非交集"""
        dense = [Doc(id="d1", fields={"content": "dense only"})]
        sparse = [SparseResult(doc_id="s1", score=1.0)]  # sparse only

        results = rrf_fuse(dense_results=dense, sparse_results=sparse, topk=10)

        ids = [r.id for r in results]
        assert "d1" in ids  # dense-only
        assert "s1" in ids  # sparse-only (之前会被丢弃)

    def test_rrf_fuse_overlapping_docs(self):
        """重叠文档的融合分数更高"""
        dense = [
            Doc(id="d1", fields={"content": "both"}),
            Doc(id="d2", fields={"content": "dense only"}),
        ]
        sparse = [
            SparseResult(doc_id="d1", score=1.0),  # 在 dense 和 sparse 都出现
            SparseResult(doc_id="s1", score=1.0),   # sparse only
        ]

        results = rrf_fuse(dense_results=dense, sparse_results=sparse, topk=10)

        # d1 在两个列表中都出现，应该有更高的融合分数
        d1_result = next(r for r in results if r.id == "d1")
        d2_result = next(r for r in results if r.id == "d2")
        assert d1_result.score > d2_result.score

    def test_rrf_fuse_accepts_tuple_sparse_results(self):
        """兼容 tuple 格式的 sparse 结果"""
        dense = [Doc(id="d1", fields={"content": "text"})]
        sparse = [("d2", 1.0)]  # tuple 格式

        results = rrf_fuse(dense_results=dense, sparse_results=sparse, topk=10)
        ids = [r.id for r in results]
        assert "d1" in ids
        assert "d2" in ids

    def test_rrf_fuse_preserves_score(self):
        """融合结果有 score"""
        dense = [Doc(id="d1", fields={"content": "text"})]
        results = rrf_fuse(dense_results=dense, sparse_results=[], topk=5)
        assert results[0].score > 0

    def test_rrf_fuse_sparse_only_with_keyword_index_has_content(self, tmp_dir):
        """sparse-only 结果通过 keyword_index 获取真实 content"""
        # 创建 KeywordIndex 并添加带 metadata 的文档
        index = KeywordIndex(index_dir=str(tmp_dir / "bm25"))
        index.init()
        index.add_documents(
            ["doc1_0"],
            ["深度学习在自然语言处理中的应用"],
            metadatas=[{"content": "深度学习在自然语言处理中的应用", "anchors": []}],
        )

        sparse = [SparseResult(doc_id="doc1_0", score=1.5)]
        results = rrf_fuse(dense_results=[], sparse_results=sparse, topk=5, keyword_index=index)

        assert len(results) == 1
        assert results[0].id == "doc1_0"
        # 关键：sparse-only 的 content 不应为空
        assert results[0].content == "深度学习在自然语言处理中的应用"

    def test_rrf_fuse_sparse_only_without_keyword_index_empty_content(self):
        """没有 keyword_index 时，sparse-only 的 content 为空"""
        sparse = [SparseResult(doc_id="s1", score=1.0)]
        results = rrf_fuse(dense_results=[], sparse_results=sparse, topk=5)

        assert len(results) == 1
        assert results[0].content == ""
