"""AnswerGenerator 测试

AG-U01: import 路径正确性
AG-U02: rrf_fuse 传了 keyword_index（精确断言）
AG-U03: 无证据时 yield 明确提示
AG-U04: 有证据时流式输出 + 历史保存
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent_layer.response.answer_generator import AnswerGenerator
from app.data_layer.data_persistence.chroma_store.vector_index import Doc
from app.data_layer.retrieval.fusion.rrf_fusion import FusedDoc


def _make_generator(**overrides):
    """构造 AnswerGenerator 实例，所有依赖默认为 MagicMock"""
    defaults = dict(
        settings=MagicMock(),
        chat_model=MagicMock(),
        vector_store=MagicMock(),
        keyword_search=MagicMock(),
        conversation_repo=MagicMock(),
        embedding_client=None,
    )
    defaults.update(overrides)
    return AnswerGenerator(**defaults)


def _mock_doc(paper_id="p1", content="测试内容", page=1, section="引言"):
    """构造 mock Doc 对象（VectorIndex 返回）"""
    return Doc(
        id=f"{paper_id}_0",
        fields={
            "paper_id": paper_id,
            "content": content,
            "source_page": page,
            "section_title": section,
            "anchor_id": f"{paper_id}_a0",
            "chunk_index": 0,
        },
        distance=0.1,
    )


def _mock_fused_doc(paper_id="p1", content="测试内容", page=1, section="引言"):
    """构造 FusedDoc 对象（rrf_fuse 实际返回类型）"""
    return FusedDoc(
        id=f"{paper_id}_0",
        content=content,
        metadata={
            "paper_id": paper_id,
            "source_page": page,
            "section_title": section,
            "anchor_id": f"{paper_id}_a0",
            "chunk_index": 0,
        },
        score=0.9,
        dense_rank=1,
        sparse_rank=1,
    )


class TestAGU01:
    """import 路径正确性"""

    def test_imports_from_data_persistence(self):
        """AnswerGenerator 从正确的路径导入 KeywordIndex 和 VectorIndex"""
        import app.agent_layer.response.answer_generator as mod
        assert hasattr(mod, "AnswerGenerator")
        assert hasattr(mod, "KeywordIndex")
        assert hasattr(mod, "VectorIndex")

    def test_module_source_path(self):
        """模块的 import 来源不是 app.data_layer.storage"""
        import app.agent_layer.response.answer_generator as mod
        import inspect
        source = inspect.getsource(mod)
        assert "app.data_layer.storage" not in source


class TestAGU02:
    """rrf_fuse 调用"""

    @pytest.mark.asyncio
    async def test_rrf_fuse_receives_keyword_index(self):
        """rrf_fuse 被调用时 keyword_index 参数精确等于 self._keyword_search"""
        keyword_search = MagicMock()
        keyword_search.query.return_value = []

        gen = _make_generator(keyword_search=keyword_search)

        with patch("app.agent_layer.response.answer_generator.fusion") as mock_fusion:
            mock_fusion.rrf_fuse.return_value = []
            [e async for e in gen.generate("sess1", "test query")]

            mock_fusion.rrf_fuse.assert_called_once()
            call_kwargs = mock_fusion.rrf_fuse.call_args.kwargs
            assert "keyword_index" in call_kwargs
            assert call_kwargs["keyword_index"] is keyword_search


class TestAGU03:
    """无证据处理"""

    @pytest.mark.asyncio
    async def test_no_evidence_yields_explicit_message(self):
        """无检索结果时 yield '未找到相关文献' 而非裸 chat"""
        gen = _make_generator()

        with patch("app.agent_layer.response.answer_generator.fusion") as mock_fusion:
            mock_fusion.rrf_fuse.return_value = []
            events = [e async for e in gen.generate("sess1", "不存在的问题")]

            event_types = [e["event"] for e in events]
            assert event_types == ["metadata", "chunk", "done"]

            content = events[1]["data"]["content"]
            assert "未找到相关文献" in content

    @pytest.mark.asyncio
    async def test_no_evidence_does_not_call_llm(self):
        """无证据时不应调用 LLM"""
        chat_model = MagicMock()
        gen = _make_generator(chat_model=chat_model)

        with patch("app.agent_layer.response.answer_generator.fusion") as mock_fusion:
            mock_fusion.rrf_fuse.return_value = []
            [e async for e in gen.generate("sess1", "不存在的问题")]

            chat_model.chat_stream.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_query_yields_error(self):
        """空查询 yield error 事件"""
        gen = _make_generator()
        events = [e async for e in gen.generate("sess1", "")]

        assert len(events) == 1
        assert events[0]["event"] == "error"


class TestAGU04:
    """有证据时的流式输出"""

    @pytest.mark.asyncio
    async def test_success_with_fused_doc(self):
        """rrf_fuse 返回 FusedDoc 时正确提取 metadata"""
        doc = _mock_fused_doc(
            paper_id="p1", content="深度学习是人工智能的一个子领域", page=3, section="方法",
        )

        chat_model = MagicMock()

        async def _fake_stream(messages):
            yield "深度学习"
            yield "是AI的子领域"

        chat_model.chat_stream = _fake_stream

        conversation_repo = MagicMock()
        conversation_repo.get_messages.return_value = []

        gen = _make_generator(
            chat_model=chat_model,
            conversation_repo=conversation_repo,
        )

        with patch("app.agent_layer.response.answer_generator.fusion") as mock_fusion:
            mock_fusion.rrf_fuse.return_value = [doc]
            events = [e async for e in gen.generate("sess1", "什么是深度学习")]

            metadata_event = next(e for e in events if e["event"] == "metadata")
            assert metadata_event["data"]["source_count"] == 1
            source = metadata_event["data"]["sources"][0]
            assert source["paper_id"] == "p1"
            assert source["page"] == 3
            assert source["section"] == "方法"

    @pytest.mark.asyncio
    async def test_success_path_yields_metadata_chunk_done(self):
        """有证据时 yield metadata -> chunk... -> done（Doc 类型）"""
        doc = _mock_doc(content="深度学习是人工智能的一个子领域")

        chat_model = MagicMock()

        async def _fake_stream(messages):
            yield "深度学习"
            yield "是AI的子领域"

        chat_model.chat_stream = _fake_stream

        conversation_repo = MagicMock()
        conversation_repo.get_messages.return_value = []

        gen = _make_generator(
            chat_model=chat_model,
            conversation_repo=conversation_repo,
        )

        with patch("app.agent_layer.response.answer_generator.fusion") as mock_fusion:
            mock_fusion.rrf_fuse.return_value = [doc]
            events = [e async for e in gen.generate("sess1", "什么是深度学习")]

            event_types = [e["event"] for e in events]
            assert event_types[0] == "metadata"
            assert events[0]["data"]["source_count"] == 1
            assert events[-1]["event"] == "done"

            # 中间是 chunk 事件
            chunk_events = [e for e in events if e["event"] == "chunk"]
            assert len(chunk_events) == 2
            assert chunk_events[0]["data"]["content"] == "深度学习"
