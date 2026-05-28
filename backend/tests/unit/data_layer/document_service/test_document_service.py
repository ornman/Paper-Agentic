"""DocumentIngestService 测试

DOC-U01: DOCX 同级支持
DOC-U02: 软删除/硬删除
DOC-U03: 文档列表
DOC-U04: IngestResult 数据结构
DOC-U05: structured.json schema 契约
DOC-U06: Unsupported suffix 拒绝
DOC-U07: rebuild_document 原子回滚
DOC-U08: visual_blocks parent_anchor_id 解析
"""

from __future__ import annotations

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.data_layer.data_persistence.document_service import (
    DocumentIngestService,
    IngestResult,
    _resolve_visual_block_anchors,
)
from app.data_layer.data_persistence.chroma_store.soft_delete import SoftDeleteManager


def _make_service(tmp_dir, **overrides):
    """构造 DocumentIngestService 实例"""
    config = overrides.get("config", MagicMock())
    vector_index = overrides.get("vector_index", MagicMock())
    keyword_index = overrides.get("keyword_index", MagicMock())
    soft_delete = overrides.get("soft_delete", None)
    dir_manager = overrides.get("dir_manager", MagicMock())

    if soft_delete is None:
        soft_delete = SoftDeleteManager(index_dir=str(tmp_dir / "soft_delete"))
        soft_delete.init()

    return DocumentIngestService(
        config=config,
        vector_index=vector_index,
        keyword_index=keyword_index,
        soft_delete_manager=soft_delete,
        directory_manager=dir_manager,
    )


def _mock_chunk(anchor_id="a1", page=1, content="test content"):
    """构造 mock chunk"""
    anchor = MagicMock()
    anchor.anchor_id = anchor_id
    anchor.source_file_path = "/test.pdf"
    anchor.doc_type = "pdf"
    anchor.page = page
    anchor.block_id = "b1"
    anchor.block_type = "text"
    anchor.heading_path = ["引言"]
    anchor.paragraph_index = 0
    anchor.char_start = 0
    anchor.char_end = 100
    anchor.bbox = [0, 0, 100, 100]
    anchor.parent_anchor_id = ""
    anchor.source_text_hash = "abc123"

    chunk = MagicMock()
    chunk.anchors = [anchor]
    chunk.content = content
    return chunk


class TestDocU01:
    """DOCX 同级支持"""

    @pytest.mark.asyncio
    async def test_docx_passes_format_check(self, tmp_dir):
        """DOCX 文件通过格式检查，进入 pipeline"""
        service = _make_service(tmp_dir)

        docx_path = tmp_dir / "test.docx"
        docx_path.write_bytes(b"fake docx")

        # Mock pipeline 使其不真正执行
        with patch(
            "app.data_layer.PDF_preprocessor_data.transfer.pipeline.PipelineOrchestrator"
        ) as MockPipeline:
            mock_instance = MagicMock()
            mock_state = MagicMock()
            mock_state.stage.value = "done"
            mock_state._chunks = []
            mock_state._final_markdown = ""
            mock_state._conversion_result = None
            mock_state._vlm_result = None
            mock_state.events = []
            mock_state.route = None
            mock_state.started_at = 0
            mock_state.completed_at = 1
            mock_instance.run = AsyncMock(return_value=mock_state)
            MockPipeline.return_value = mock_instance

            result = await service.ingest_document(docx_path)

            # pipeline 应该被调用（DOCX 没有被格式检查拒绝）
            mock_instance.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_docx_accepted_suffixes(self, tmp_dir):
        """所有 MinerU 支持的后缀都通过格式检查进入 pipeline"""
        service = _make_service(tmp_dir)
        supported = [".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".ppt", ".xls"]

        with patch(
            "app.data_layer.PDF_preprocessor_data.transfer.pipeline.PipelineOrchestrator"
        ) as MockPipeline:
            mock_instance = MagicMock()
            mock_state = MagicMock()
            mock_state.stage.value = "done"
            mock_state._chunks = []
            mock_state._final_markdown = ""
            mock_state._conversion_result = None
            mock_state._vlm_result = None
            mock_state.events = []
            mock_state.route = None
            mock_state.started_at = 0
            mock_state.completed_at = 1
            mock_instance.run = AsyncMock(return_value=mock_state)
            MockPipeline.return_value = mock_instance

            for suffix in supported:
                mock_instance.run.reset_mock()
                file_path = tmp_dir / f"test{suffix}"
                file_path.write_bytes(b"fake")
                result = await service.ingest_document(file_path)
                assert "不支持的文件格式" not in (result.error or ""), f"{suffix} 被错误拒绝"
                mock_instance.run.assert_called_once(), f"{suffix} 未进入 pipeline"

    @pytest.mark.asyncio
    async def test_nonexistent_file_returns_failure(self, tmp_dir):
        """不存在的文件返回 failure"""
        service = _make_service(tmp_dir)
        result = await service.ingest_document(Path("/nonexistent/file.pdf"))
        assert result.success is False
        assert "不存在" in result.error


class TestDocU02:
    """软删除/硬删除"""

    def test_soft_delete_marks_record(self, tmp_dir):
        """软删除标记记录但不移除索引"""
        vector_index = MagicMock()
        keyword_index = MagicMock()
        service = _make_service(tmp_dir, vector_index=vector_index, keyword_index=keyword_index)

        service.delete_document("test_paper")

        assert service._soft_delete_manager.is_deleted("test_paper") is True
        vector_index.delete_paper.assert_not_called()
        keyword_index.delete_paper.assert_not_called()

    def test_hard_delete_removes_from_index(self, tmp_dir):
        """硬删除从索引和文件系统移除"""
        vector_index = MagicMock()
        keyword_index = MagicMock()
        dir_manager = MagicMock()
        service = _make_service(tmp_dir, vector_index=vector_index, keyword_index=keyword_index, dir_manager=dir_manager)

        service.hard_delete_document("test_paper")

        vector_index.delete_paper.assert_called_once_with("test_paper")
        keyword_index.delete_paper.assert_called_once_with("test_paper")
        dir_manager.delete_document.assert_called_once_with("test_paper")


class TestDocU03:
    """文档列表"""

    def test_list_documents(self, tmp_dir):
        """列出已导入文档"""
        papers_dir = tmp_dir / "papers"
        parsed_dir = tmp_dir / "parsed"
        papers_dir.mkdir()
        parsed_dir.mkdir()

        paper_dir = papers_dir / "test_paper"
        paper_dir.mkdir()
        (paper_dir / "test.pdf").write_bytes(b"fake pdf")

        from app.data_layer.data_persistence.file_management.directory_manager import DirectoryManager
        dir_manager = DirectoryManager(
            papers_dir=str(papers_dir),
            parsed_dir=str(parsed_dir),
            backups_dir=str(tmp_dir / "backups"),
        )

        service = _make_service(tmp_dir, dir_manager=dir_manager)
        docs = service.list_documents()

        assert len(docs) == 1
        assert docs[0]["paper_id"] == "test_paper"
        assert docs[0]["is_deleted"] is False
        assert "test.pdf" in docs[0]["files"]


class TestDocU04:
    """IngestResult 数据结构"""

    def test_ingest_result_fields(self):
        result = IngestResult(
            paper_id="test", success=True, chunk_count=5, elapsed_s=1.5,
            structured_path="/path/to/structured.json", report_path="/path/to/report.json",
        )
        assert result.paper_id == "test"
        assert result.success is True
        assert result.chunk_count == 5
        assert result.elapsed_s == 1.5
        assert result.structured_path == "/path/to/structured.json"
        assert result.report_path == "/path/to/report.json"
        assert result.error is None
        assert result.logs == []

    def test_ingest_result_failure(self):
        result = IngestResult(paper_id="test", success=False, error="something went wrong")
        assert result.success is False
        assert result.error == "something went wrong"


class TestDocU05:
    """structured.json schema 契约"""

    def test_build_structured_has_required_fields(self, tmp_dir):
        """_build_structured 输出包含所有核心字段"""
        from app.data_layer.data_persistence.file_management.directory_manager import DirectoryManager
        dir_manager = DirectoryManager(
            papers_dir=str(tmp_dir / "papers"),
            parsed_dir=str(tmp_dir / "parsed"),
            backups_dir=str(tmp_dir / "backups"),
        )
        service = _make_service(tmp_dir, dir_manager=dir_manager)

        chunk = _mock_chunk()
        metadata = {
            "doc_type": "pdf",
            "source_file_path": "/test/paper.pdf",
            "file_name": "paper.pdf",
            "page_count": 10,
            "char_count": 5000,
        }
        dir_manager.create_document_dirs("test_paper")
        structured = service._build_structured("test_paper", [chunk], metadata)

        # 顶层字段
        required_top = ["document_id", "paper_id", "doc_type", "source_file_path",
                        "pipeline_version", "markdown_path", "images_dir",
                        "doc_level", "anchors", "visual_blocks", "stats"]
        for field in required_top:
            assert field in structured, f"缺少顶层字段: {field}"

        assert structured["document_id"] == "test_paper"
        assert structured["paper_id"] == "test_paper"
        assert structured["doc_type"] == "pdf"
        assert structured["source_file_path"] == "/test/paper.pdf"
        assert isinstance(structured["pipeline_version"], str)
        assert len(structured["pipeline_version"]) > 0

        # doc_level 子字段
        dl = structured["doc_level"]
        assert dl["file_name"] == "paper.pdf"
        assert dl["page_count"] == 10
        assert dl["char_count"] == 5000

        # anchors 子字段
        assert len(structured["anchors"]) == 1
        a = structured["anchors"][0]
        assert a["anchor_id"] == "a1"
        assert a["page"] == 1
        assert a["heading_path"] == ["引言"]
        assert a["bbox"] == [0, 0, 100, 100]

        # stats
        assert structured["stats"]["chunk_count"] == 1
        assert structured["stats"]["anchor_count"] == 1

    def test_build_structured_docx_metadata(self, tmp_dir):
        """DOCX 文件的 structured.json doc_type 正确"""
        from app.data_layer.data_persistence.file_management.directory_manager import DirectoryManager
        dir_manager = DirectoryManager(
            papers_dir=str(tmp_dir / "papers"),
            parsed_dir=str(tmp_dir / "parsed"),
            backups_dir=str(tmp_dir / "backups"),
        )
        service = _make_service(tmp_dir, dir_manager=dir_manager)

        chunk = _mock_chunk()
        metadata = {
            "doc_type": "docx",
            "source_file_path": "/test/paper.docx",
            "file_name": "paper.docx",
        }
        dir_manager.create_document_dirs("test_docx")
        structured = service._build_structured("test_docx", [chunk], metadata)

        assert structured["doc_type"] == "docx"
        assert structured["source_file_path"] == "/test/paper.docx"
        assert structured["doc_level"]["file_name"] == "paper.docx"


class TestDocU06:
    """Unsupported suffix 拒绝"""

    @pytest.mark.asyncio
    async def test_unsupported_suffix_rejected(self, tmp_dir):
        """不支持的文件格式（如 .txt）被拒绝"""
        service = _make_service(tmp_dir)
        txt_path = tmp_dir / "test.txt"
        txt_path.write_text("hello")

        result = await service.ingest_document(txt_path)

        assert result.success is False
        assert "不支持的文件格式" in result.error


class TestDocU07:
    """rebuild_document 原子回滚"""

    @pytest.mark.asyncio
    async def test_rebuild_failure_preserves_old_index(self, tmp_dir):
        """重建失败时旧索引保留，不丢数据"""
        vector_index = MagicMock()
        keyword_index = MagicMock()

        papers_dir = tmp_dir / "papers"
        parsed_dir = tmp_dir / "parsed"
        papers_dir.mkdir()
        parsed_dir.mkdir()

        paper_dir = papers_dir / "test_paper"
        paper_dir.mkdir()
        (paper_dir / "test.pdf").write_bytes(b"fake pdf")

        from app.data_layer.data_persistence.file_management.directory_manager import DirectoryManager
        dir_manager = DirectoryManager(
            papers_dir=str(papers_dir),
            parsed_dir=str(parsed_dir),
            backups_dir=str(tmp_dir / "backups"),
        )

        service = _make_service(
            tmp_dir, vector_index=vector_index, keyword_index=keyword_index, dir_manager=dir_manager,
        )

        # Mock ingest_document 返回失败
        with patch.object(service, "ingest_document", new_callable=AsyncMock) as mock_ingest:
            mock_ingest.return_value = IngestResult(
                paper_id="test_paper__rebuild_tmp", success=False, error="pipeline 失败",
            )
            result = await service.rebuild_document("test_paper")

        assert result.success is False
        assert result.error == "pipeline 失败"

        # 旧索引的 delete_paper 不应该被调用（失败时不动旧索引）
        for call in vector_index.delete_paper.call_args_list:
            assert call[0][0] != "test_paper", "旧索引不应被删除"
        for call in keyword_index.delete_paper.call_args_list:
            assert call[0][0] != "test_paper", "旧索引不应被删除"

        # 临时索引应该被清理
        vector_index.delete_paper.assert_any_call("test_paper__rebuild_tmp")
        keyword_index.delete_paper.assert_any_call("test_paper__rebuild_tmp")

    @pytest.mark.asyncio
    async def test_rebuild_success_replaces_old_index(self, tmp_dir):
        """重建成功时旧索引被替换"""
        vector_index = MagicMock()
        keyword_index = MagicMock()

        papers_dir = tmp_dir / "papers"
        parsed_dir = tmp_dir / "parsed"
        papers_dir.mkdir()
        parsed_dir.mkdir()

        paper_dir = papers_dir / "test_paper"
        paper_dir.mkdir()
        (paper_dir / "test.pdf").write_bytes(b"fake pdf")

        from app.data_layer.data_persistence.file_management.directory_manager import DirectoryManager
        dir_manager = DirectoryManager(
            papers_dir=str(papers_dir),
            parsed_dir=str(parsed_dir),
            backups_dir=str(tmp_dir / "backups"),
        )

        service = _make_service(
            tmp_dir, vector_index=vector_index, keyword_index=keyword_index, dir_manager=dir_manager,
        )

        with patch.object(service, "ingest_document", new_callable=AsyncMock) as mock_ingest:
            mock_ingest.return_value = IngestResult(
                paper_id="test_paper__rebuild_tmp", success=True, chunk_count=5,
            )
            result = await service.rebuild_document("test_paper")

        assert result.success is True
        assert result.chunk_count == 5
        assert result.paper_id == "test_paper"

        # 新流程：rename tmp→backup, rename backup→paper_id
        # 不再先删旧索引
        calls = vector_index.rename_paper.call_args_list
        assert calls[0] == (("test_paper__rebuild_tmp", "test_paper__rebuild_backup"),)
        assert calls[1] == (("test_paper__rebuild_backup", "test_paper"),)

        # 成功后清理 backup
        vector_index.delete_paper.assert_any_call("test_paper__rebuild_backup")
        keyword_index.delete_paper.assert_any_call("test_paper__rebuild_backup")

    @pytest.mark.asyncio
    async def test_rebuild_cleans_tmp_parsed_dir(self, tmp_dir):
        """重建成功后临时 parsed 目录被清理"""
        vector_index = MagicMock()
        keyword_index = MagicMock()

        papers_dir = tmp_dir / "papers"
        parsed_dir = tmp_dir / "parsed"
        papers_dir.mkdir()
        parsed_dir.mkdir()

        paper_dir = papers_dir / "test_paper"
        paper_dir.mkdir()
        (paper_dir / "test.pdf").write_bytes(b"fake pdf")

        from app.data_layer.data_persistence.file_management.directory_manager import DirectoryManager
        dir_manager = DirectoryManager(
            papers_dir=str(papers_dir),
            parsed_dir=str(parsed_dir),
            backups_dir=str(tmp_dir / "backups"),
        )

        service = _make_service(
            tmp_dir, vector_index=vector_index, keyword_index=keyword_index, dir_manager=dir_manager,
        )

        # ingest_document 成功后会创建 tmp parsed 目录
        tmp_parsed = parsed_dir / "test_paper__rebuild_tmp"
        tmp_parsed.mkdir()
        (tmp_parsed / "markdown.json").write_text("{}")

        with patch.object(service, "ingest_document", new_callable=AsyncMock) as mock_ingest:
            mock_ingest.return_value = IngestResult(
                paper_id="test_paper__rebuild_tmp", success=True, chunk_count=5,
            )
            await service.rebuild_document("test_paper")

        assert not tmp_parsed.exists(), "临时 parsed 目录应被清理"

    @pytest.mark.asyncio
    async def test_rebuild_rename_failure_preserves_old(self, tmp_dir):
        """rename backup→paper_id 失败时旧索引保留（rename 是 additive，不删旧条目）"""
        vector_index = MagicMock()
        keyword_index = MagicMock()

        # 第二次 rename（backup→paper_id）失败
        call_count = {"n": 0}
        original_rename = vector_index.rename_paper

        def _fail_on_second_rename(old, new):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("chroma error")

        vector_index.rename_paper.side_effect = _fail_on_second_rename

        papers_dir = tmp_dir / "papers"
        parsed_dir = tmp_dir / "parsed"
        papers_dir.mkdir()
        parsed_dir.mkdir()

        paper_dir = papers_dir / "test_paper"
        paper_dir.mkdir()
        (paper_dir / "test.pdf").write_bytes(b"fake pdf")

        from app.data_layer.data_persistence.file_management.directory_manager import DirectoryManager
        dir_manager = DirectoryManager(
            papers_dir=str(papers_dir),
            parsed_dir=str(parsed_dir),
            backups_dir=str(tmp_dir / "backups"),
        )

        service = _make_service(
            tmp_dir, vector_index=vector_index, keyword_index=keyword_index, dir_manager=dir_manager,
        )

        with patch.object(service, "ingest_document", new_callable=AsyncMock) as mock_ingest:
            mock_ingest.return_value = IngestResult(
                paper_id="test_paper__rebuild_tmp", success=True, chunk_count=5,
            )
            result = await service.rebuild_document("test_paper")

        assert result.success is False
        assert "rename backup→final 失败" in result.error

        # 旧索引 delete_paper 不应被调用（新流程不再先删旧）
        for call in vector_index.delete_paper.call_args_list:
            assert call[0][0] != "test_paper", "旧索引不应被删除"

        # backup 应被清理
        vector_index.delete_paper.assert_any_call("test_paper__rebuild_backup")
        keyword_index.delete_paper.assert_any_call("test_paper__rebuild_backup")


class TestDocU08:
    """visual_blocks parent_anchor_id 解析"""

    def test_resolve_visual_block_anchors_by_proximity(self):
        """按 page + bbox 空间距离匹配最近的 anchor"""
        visual_blocks = [
            {"page": 1, "bbox": [10, 10, 50, 50], "type": "image"},
        ]
        anchors = [
            {"anchor_id": "a1", "page": 1, "bbox": [20, 20, 60, 60]},
            {"anchor_id": "a2", "page": 2, "bbox": [10, 10, 50, 50]},
        ]

        resolved = _resolve_visual_block_anchors(visual_blocks, [], anchors)

        assert len(resolved) == 1
        assert resolved[0]["parent_anchor_id"] == "a1"

    def test_resolve_visual_block_anchors_already_has_parent(self):
        """已有 parent_anchor_id 的 visual_block 不重新解析"""
        visual_blocks = [
            {"page": 1, "bbox": [10, 10, 50, 50], "parent_anchor_id": "existing"},
        ]
        anchors = [
            {"anchor_id": "a1", "page": 1, "bbox": [10, 10, 50, 50]},
        ]

        resolved = _resolve_visual_block_anchors(visual_blocks, [], anchors)

        assert resolved[0]["parent_anchor_id"] == "existing"

    def test_resolve_visual_block_anchors_page_mismatch(self):
        """不同 page 的 anchor 不匹配，parent_anchor_id 为空"""
        visual_blocks = [
            {"page": 1, "bbox": [10, 10, 50, 50]},
        ]
        anchors = [
            {"anchor_id": "a1", "page": 2, "bbox": [10, 10, 50, 50]},
        ]

        resolved = _resolve_visual_block_anchors(visual_blocks, [], anchors)

        # 不同 page 的 anchor 被跳过，parent_anchor_id 为空
        assert resolved[0]["parent_anchor_id"] == ""

    def test_resolve_visual_block_anchors_empty(self):
        """空列表返回空"""
        resolved = _resolve_visual_block_anchors([], [], [])
        assert resolved == []
