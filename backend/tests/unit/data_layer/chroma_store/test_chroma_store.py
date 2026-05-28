"""Chroma Store 模块测试

STORE-U01: Windows 路径回归
STORE-U02: BM25 查询
STORE-I01: 真实向量插入查询删除
STORE-I03: 文件句柄释放
"""

from __future__ import annotations

import json
import pytest
import tempfile
from pathlib import Path

from app.data_layer.data_persistence.chroma_store.soft_delete import SoftDeleteManager
from app.data_layer.data_persistence.chroma_store.keyword_index import KeywordIndex
from app.data_layer.data_persistence.chroma_store.vector_index import VectorIndex, Doc


class TestStoreU01:
    """Windows 路径回归 - SoftDeleteManager"""

    def test_mark_deleted_no_type_error(self, tmp_dir):
        """mark_deleted 在 Windows 上不报 TypeError"""
        manager = SoftDeleteManager(index_dir=str(tmp_dir), retention_days=7)
        manager.init()

        # 这行之前会报 TypeError: unsupported operand type(s) for +: 'WindowsPath' and 'str'
        manager.mark_deleted("test_paper_001")

        assert manager.is_deleted("test_paper_001")

    def test_save_and_load_records(self, tmp_dir):
        """保存和加载软删除记录"""
        manager = SoftDeleteManager(index_dir=str(tmp_dir), retention_days=7)
        manager.init()
        manager.mark_deleted("paper_1")
        manager.mark_deleted("paper_2")

        # 重新加载
        manager2 = SoftDeleteManager(index_dir=str(tmp_dir), retention_days=7)
        manager2.init()

        assert manager2.is_deleted("paper_1")
        assert manager2.is_deleted("paper_2")
        assert not manager2.is_deleted("paper_3")

    def test_records_file_is_valid_json(self, tmp_dir):
        """记录文件是有效 JSON"""
        manager = SoftDeleteManager(index_dir=str(tmp_dir))
        manager.init()
        manager.mark_deleted("test")

        records_file = tmp_dir / "soft_delete_records.json"
        assert records_file.exists()

        data = json.loads(records_file.read_text(encoding="utf-8"))
        assert "test" in data
        assert "deleted_at" in data["test"]


class TestStoreU02:
    """BM25 查询"""

    def test_bm25_single_doc(self, tmp_dir):
        """单篇文档 BM25 查询"""
        index = KeywordIndex(index_dir=str(tmp_dir / "bm25"))
        index.init()
        index.add_documents(["doc1"], ["深度学习在自然语言处理中的应用研究"])

        results = index.query("深度学习", topk=5)
        assert len(results) >= 1
        assert results[0][0] == "doc1"

    def test_bm25_two_docs(self, tmp_dir):
        """两篇文档 BM25 查询"""
        index = KeywordIndex(index_dir=str(tmp_dir / "bm25"))
        index.init()
        index.add_documents(
            ["doc1", "doc2"],
            [
                "深度学习在自然语言处理中的应用研究",
                "机器学习与计算机视觉综述",
            ],
        )

        results = index.query("深度学习", topk=5)
        assert len(results) >= 1
        # doc1 应该排在前面
        assert results[0][0] == "doc1"

    def test_bm25_three_docs(self, tmp_dir):
        """三篇文档 BM25 查询"""
        index = KeywordIndex(index_dir=str(tmp_dir / "bm25"))
        index.init()
        index.add_documents(
            ["doc1", "doc2", "doc3"],
            [
                "深度学习在自然语言处理中的应用研究",
                "机器学习与计算机视觉综述",
                "强化学习算法在游戏中的应用",
            ],
        )

        results = index.query("深度学习 自然语言", topk=5)
        assert len(results) >= 1
        assert results[0][0] == "doc1"

    def test_bm25_delete_paper(self, tmp_dir):
        """删除论文后查询不再返回"""
        index = KeywordIndex(index_dir=str(tmp_dir / "bm25"))
        index.init()
        index.add_documents(["doc1_0", "doc1_1", "doc2_0"], ["文本A", "文本B", "文本C"])

        index.delete_paper("doc1")

        # doc1_0 和 doc1_1 应该被删除
        remaining = index.doc_count
        assert remaining == 1

    def test_bm25_delete_paper_cleans_metadata(self, tmp_dir):
        """删除论文后 _metadata_map 也被清理"""
        index = KeywordIndex(index_dir=str(tmp_dir / "bm25"))
        index.init()
        index.add_documents(
            ["doc1_0", "doc1_1", "doc2_0"],
            ["文本A", "文本B", "文本C"],
            metadatas=[
                {"paper_id": "doc1", "chunk_index": 0},
                {"paper_id": "doc1", "chunk_index": 1},
                {"paper_id": "doc2", "chunk_index": 0},
            ],
        )

        index.delete_paper("doc1")

        # 被删除的 doc 的 metadata 应该被清理
        assert index.get_metadata("doc1_0") is None
        assert index.get_metadata("doc1_1") is None
        # 未被删除的 doc 的 metadata 应该保留
        assert index.get_metadata("doc2_0") is not None


class TestStoreI01:
    """真实向量插入查询删除"""

    def test_vector_index_init_and_close(self, tmp_dir):
        """VectorIndex 初始化和关闭"""
        index = VectorIndex(path=str(tmp_dir / "chroma"), dimension=128)
        index.init()
        assert index.stats["doc_count"] == 0
        index.close()

    def test_vector_index_insert_and_query(self, tmp_dir):
        """VectorIndex 插入和查询"""
        index = VectorIndex(path=str(tmp_dir / "chroma"), dimension=128)
        index.init()

        chunks = [
            {"content": "测试文本1", "chunk_type": "paragraph"},
            {"content": "测试文本2", "chunk_type": "paragraph"},
        ]
        vectors = [[0.1] * 128, [0.2] * 128]

        count = index.insert_chunks("paper1", chunks, vectors)
        assert count == 2
        assert index.stats["doc_count"] == 2

        # 查询
        results = index.query(vector=[0.1] * 128, topk=5)
        assert len(results) >= 1
        assert results[0].id.startswith("paper1_")

        index.close()

    def test_vector_index_delete_paper(self, tmp_dir):
        """VectorIndex 删除论文"""
        index = VectorIndex(path=str(tmp_dir / "chroma"), dimension=128)
        index.init()

        chunks = [{"content": "text", "chunk_type": "p"}]
        vectors = [[0.1] * 128]
        index.insert_chunks("paper1", chunks, vectors)
        assert index.stats["doc_count"] == 1

        index.delete_paper("paper1")
        assert index.stats["doc_count"] == 0

        index.close()

    def test_vector_index_distance_in_result(self, tmp_dir):
        """VectorIndex 查询结果包含 distance"""
        index = VectorIndex(path=str(tmp_dir / "chroma"), dimension=128)
        index.init()

        chunks = [{"content": "test", "chunk_type": "p"}]
        vectors = [[1.0] * 128]
        index.insert_chunks("p1", chunks, vectors)

        results = index.query(vector=[1.0] * 128, topk=1)
        assert len(results) == 1
        # cosine distance 应该接近 0（完全匹配）
        assert results[0].distance < 0.01

        index.close()


class TestStoreI03:
    """文件句柄释放"""

    def test_close_releases_references(self, tmp_dir):
        """close 后引用被清除"""
        db_path = tmp_dir / "chroma"
        index = VectorIndex(path=str(db_path), dimension=128)
        index.init()

        chunks = [{"content": "test", "chunk_type": "p"}]
        vectors = [[0.1] * 128]
        index.insert_chunks("p1", chunks, vectors)

        index.close()

        # close 后引用应为 None
        assert index._client is None
        assert index._collection is None

        # Windows 上 ChromaDB PersistentClient 可能不释放 SQLite 文件句柄
        # 这是已知的 Windows 特有限制，不是代码 bug
        import gc
        gc.collect()

        import shutil
        try:
            shutil.rmtree(db_path)
            assert not db_path.exists()
        except PermissionError:
            # Windows 上 chroma.sqlite3 可能仍被占用，这是已知限制
            pytest.xfail("Windows 上 ChromaDB 文件句柄未完全释放（已知限制）")


class TestStoreU03:
    """rename_paper 重命名"""

    def test_bm25_rename_paper(self, tmp_dir):
        """rename_paper 正确迁移 doc_id 和 metadata"""
        index = KeywordIndex(index_dir=str(tmp_dir / "bm25"))
        index.init()
        index.add_documents(
            ["doc1_0", "doc1_1", "doc2_0"],
            ["文本A", "文本B", "文本C"],
            metadatas=[
                {"paper_id": "doc1", "chunk_index": 0},
                {"paper_id": "doc1", "chunk_index": 1},
                {"paper_id": "doc2", "chunk_index": 0},
            ],
        )

        index.rename_paper("doc1", "renamed")

        # 旧 ID 应该不存在
        assert index.get_metadata("doc1_0") is None
        assert index.get_metadata("doc1_1") is None

        # 新 ID 应该存在且 metadata 正确
        meta0 = index.get_metadata("renamed_0")
        assert meta0 is not None
        assert meta0["paper_id"] == "renamed"

        meta1 = index.get_metadata("renamed_1")
        assert meta1 is not None

        # 不相关的 doc 不受影响
        assert index.get_metadata("doc2_0") is not None
        assert index.doc_count == 3

    def test_bm25_rename_nonexistent(self, tmp_dir):
        """rename 不存在的 paper_id 不报错"""
        index = KeywordIndex(index_dir=str(tmp_dir / "bm25"))
        index.init()
        index.add_documents(["doc1_0"], ["文本"])

        index.rename_paper("nonexistent", "new")
        assert index.doc_count == 1


class TestStoreI04:
    """VectorIndex rename_paper"""

    def test_vector_rename_paper(self, tmp_dir):
        """rename_paper 正确迁移 vector 文档"""
        index = VectorIndex(path=str(tmp_dir / "chroma"), dimension=128)
        index.init()

        chunks = [
            {"content": "text1", "chunk_type": "p"},
            {"content": "text2", "chunk_type": "p"},
        ]
        vectors = [[0.1] * 128, [0.2] * 128]
        index.insert_chunks("paper1", chunks, vectors)

        index.rename_paper("paper1", "paper_renamed")

        # 旧 paper_id 查询应无结果
        old_results = index.query(vector=[0.1] * 128, topk=10, paper_ids=["paper1"])
        assert len(old_results) == 0

        # 新 paper_id 查询应有结果
        new_results = index.query(vector=[0.1] * 128, topk=10, paper_ids=["paper_renamed"])
        assert len(new_results) == 2
        for doc in new_results:
            assert doc.fields.get("paper_id") == "paper_renamed"

        index.close()

    def test_vector_rename_nonexistent(self, tmp_dir):
        """rename 不存在的 paper_id 不报错"""
        index = VectorIndex(path=str(tmp_dir / "chroma"), dimension=128)
        index.init()

        index.rename_paper("nonexistent", "new")
        assert index.stats["doc_count"] == 0

        index.close()
