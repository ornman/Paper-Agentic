"""_assemble_query 单元测试

覆盖四种权重组合 + 空输入 + 零权重。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class _FakeUsedInputs:
    def __init__(self, prompt: float = 0.0, selection: float = 0.0, written_context: float = 0.0):
        self.prompt = prompt
        self.selection = selection
        self.written_context = written_context


class _FakeSnapshot:
    def __init__(
        self,
        prompt: str = "",
        selection: str = "",
        written_context: str = "",
        prompt_w: float = 0.0,
        selection_w: float = 0.0,
        written_context_w: float = 0.0,
    ):
        self.prompt = prompt
        self.selection = selection
        self.written_context = written_context
        self.used_inputs = _FakeUsedInputs(prompt_w, selection_w, written_context_w)


def _make_runner():
    """构造 TurnRunner 实例，依赖全部 mock"""
    from app.agent_layer.orchestration.turn_runner import TurnRunner

    return TurnRunner(
        chat_model=MagicMock(),
        snapshot_builder=MagicMock(),
        retrieval_gate=MagicMock(),
        source_mapper=MagicMock(),
        block_streamer=MagicMock(),
        window_store=MagicMock(),
        editor_context_store=MagicMock(),
        persistence=MagicMock(),
    )


class TestAssembleQueryOnlyPrompt:
    def test_only_prompt(self):
        runner = _make_runner()
        snap = _FakeSnapshot(prompt="什么是 RAG？", prompt_w=1.0)
        result = runner._assemble_query(snap)
        assert result == "什么是 RAG？"

    def test_only_prompt_with_others_empty(self):
        runner = _make_runner()
        snap = _FakeSnapshot(prompt="什么是 RAG？", prompt_w=1.0, selection_w=0.0, written_context_w=0.0)
        result = runner._assemble_query(snap)
        assert result == "什么是 RAG？"


class TestAssembleQueryOnlyWrittenContext:
    def test_only_written_context(self):
        runner = _make_runner()
        snap = _FakeSnapshot(written_context="用户正在写论文", written_context_w=1.0)
        result = runner._assemble_query(snap)
        assert result == "用户已写内容：用户正在写论文"


class TestAssembleQueryWrittenContextAndSelection:
    def test_selection_before_written_context(self):
        runner = _make_runner()
        snap = _FakeSnapshot(
            selection="选中的文本",
            written_context="用户正在写论文",
            selection_w=0.7,
            written_context_w=0.3,
        )
        result = runner._assemble_query(snap)
        lines = result.split("\n\n")
        assert len(lines) == 2
        assert lines[0] == "用户圈选的文本：选中的文本"
        assert lines[1] == "用户已写内容：用户正在写论文"

    def test_written_context_before_selection_when_higher_weight(self):
        runner = _make_runner()
        snap = _FakeSnapshot(
            selection="选中的文本",
            written_context="用户正在写论文",
            selection_w=0.3,
            written_context_w=0.7,
        )
        result = runner._assemble_query(snap)
        lines = result.split("\n\n")
        assert lines[0] == "用户已写内容：用户正在写论文"
        assert lines[1] == "用户圈选的文本：选中的文本"


class TestAssembleQueryAllThree:
    def test_prompt_first(self):
        runner = _make_runner()
        snap = _FakeSnapshot(
            prompt="什么是 RAG？",
            selection="选中的文本",
            written_context="用户正在写论文",
            prompt_w=0.5,
            selection_w=0.3,
            written_context_w=0.2,
        )
        result = runner._assemble_query(snap)
        lines = result.split("\n\n")
        assert len(lines) == 3
        assert lines[0] == "什么是 RAG？"
        assert lines[1] == "用户圈选的文本：选中的文本"
        assert lines[2] == "用户已写内容：用户正在写论文"


class TestAssembleQueryEdgeCases:
    def test_empty_inputs_excluded(self):
        runner = _make_runner()
        snap = _FakeSnapshot(prompt="", selection="", written_context="", prompt_w=1.0)
        result = runner._assemble_query(snap)
        assert result == ""

    def test_zero_weight_still_included_if_text_present(self):
        runner = _make_runner()
        snap = _FakeSnapshot(prompt="问题", selection="选中文本", prompt_w=1.0, selection_w=0.0)
        result = runner._assemble_query(snap)
        assert "问题" in result
        assert "用户圈选的文本：选中文本" in result

    def test_only_empty_prompt_excluded(self):
        runner = _make_runner()
        snap = _FakeSnapshot(
            prompt="",
            selection="选中文本",
            selection_w=0.7,
        )
        result = runner._assemble_query(snap)
        assert result == "用户圈选的文本：选中文本"
