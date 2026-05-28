from __future__ import annotations

from app.agent_layer.contracts.query import AskRequest
from app.agent_layer.planning.snapshot_builder import build_snapshot


def _make_request(**kwargs):
    defaults = {"session_id": "s1", "prompt": ""}
    defaults.update(kwargs)
    return AskRequest(**defaults)


class TestBuildSnapshot:
    def test_prompt_only(self):
        req = _make_request(prompt="什么是 RAG？")
        snap = build_snapshot(req, None, [], "")
        assert snap.prompt == "什么是 RAG？"
        assert snap.used_inputs.prompt == 1.0
        assert snap.used_inputs.selection == 0.0
        assert snap.used_inputs.written_context == 0.0

    def test_written_context_only(self):
        req = _make_request(prompt="")
        ctx = {"draft": "我的论文摘要"}
        snap = build_snapshot(req, ctx, [], "")
        assert snap.written_context == "我的论文摘要"
        assert snap.used_inputs.written_context == 1.0
        assert snap.used_inputs.prompt == 0.0

    def test_written_context_and_selection(self):
        req = _make_request(prompt="", selection="选中的段落")
        ctx = {"draft": "草稿"}
        snap = build_snapshot(req, ctx, [], "")
        assert snap.used_inputs.selection == 0.7
        assert snap.used_inputs.written_context == 0.3
        assert snap.used_inputs.prompt == 0.0

    def test_all_three_sources(self):
        req = _make_request(prompt="请帮我改写", selection="选中文本")
        ctx = {"draft": "草稿内容"}
        snap = build_snapshot(req, ctx, [], "")
        assert snap.used_inputs.prompt == 0.5
        assert snap.used_inputs.selection == 0.3
        assert snap.used_inputs.written_context == 0.2

    def test_editor_context_none(self):
        req = _make_request(prompt="hello")
        snap = build_snapshot(req, None, [], "")
        assert snap.written_context == ""
        assert snap.used_inputs.prompt == 1.0

    def test_editor_context_with_content_key(self):
        req = _make_request(prompt="")
        ctx = {"content": "通过 content 字段传入"}
        snap = build_snapshot(req, ctx, [], "")
        assert snap.written_context == "通过 content 字段传入"

    def test_editor_context_empty_draft_fallback(self):
        req = _make_request(prompt="")
        ctx = {"draft": "", "content": "fallback"}
        snap = build_snapshot(req, ctx, [], "")
        assert snap.written_context == "fallback"

    def test_frozen_at_auto_filled(self):
        req = _make_request(prompt="q")
        snap = build_snapshot(req, None, [], "")
        assert snap.frozen_at is not None

    def test_request_id_unique(self):
        req = _make_request(prompt="q")
        snap1 = build_snapshot(req, None, [], "")
        snap2 = build_snapshot(req, None, [], "")
        assert snap1.request_id != snap2.request_id

    def test_paper_ids_from_request(self):
        req = _make_request(prompt="q", paper_ids=["p1", "p2"])
        snap = build_snapshot(req, None, [], "")
        assert snap.paper_ids == ["p1", "p2"]

    def test_paper_ids_none_defaults_empty(self):
        req = _make_request(prompt="q", paper_ids=None)
        snap = build_snapshot(req, None, [], "")
        assert snap.paper_ids == []

    def test_recent_window_and_history(self):
        req = _make_request(prompt="q")
        window = [{"role": "user", "content": "prev"}]
        snap = build_snapshot(req, None, window, "之前聊过 RAG")
        assert snap.recent_window == window
        assert snap.history_summary == "之前聊过 RAG"
