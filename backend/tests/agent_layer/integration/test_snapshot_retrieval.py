"""snapshot_builder → retrieval_gate 联动集成测试"""

from __future__ import annotations

import pytest

from app.agent_layer.contracts.query import AskRequest
from app.agent_layer.planning.retrieval_gate import should_retrieve
from app.agent_layer.planning.snapshot_builder import build_snapshot


# ── retrieval_gate 联动 ──────────────────────────────────────────────


async def test_no_rag_when_disabled():
    """enable_rag=False → should_retrieve 返回 False"""
    req = AskRequest(session_id="s1", prompt="hello", enable_rag=False)
    snap = build_snapshot(req, None, [], "")
    assert should_retrieve(snap) is False


async def test_rag_with_paper_ids():
    """有 paper_ids → should_retrieve 返回 True"""
    req = AskRequest(session_id="s1", prompt="hello", enable_rag=True, paper_ids=["p1"])
    snap = build_snapshot(req, None, [], "")
    assert should_retrieve(snap) is True


async def test_rag_with_selection():
    """有 selection → should_retrieve 返回 True"""
    req = AskRequest(session_id="s1", prompt="", enable_rag=True, selection="选中文字")
    snap = build_snapshot(req, {"draft": "草稿"}, [], "")
    assert should_retrieve(snap) is True


async def test_no_rag_no_inputs():
    """enable_rag=True 但 paper_ids=None 且 selection 为空 → False"""
    req = AskRequest(session_id="s1", prompt="", enable_rag=True, paper_ids=None)
    snap = build_snapshot(req, None, [], "")
    assert should_retrieve(snap) is False


# ── snapshot 权重分配 ────────────────────────────────────────────────


async def test_snapshot_weights_prompt_only():
    """只有 prompt → prompt=1.0，其余 0"""
    req = AskRequest(session_id="s1", prompt="hello")
    snap = build_snapshot(req, None, [], "")
    assert snap.used_inputs.prompt == 1.0
    assert snap.used_inputs.selection == 0.0
    assert snap.used_inputs.written_context == 0.0


async def test_snapshot_weights_all_three():
    """三源都有 → prompt=0.5, selection=0.3, written=0.2"""
    req = AskRequest(session_id="s1", prompt="改写", selection="选中文本")
    snap = build_snapshot(req, {"draft": "草稿"}, [], "")
    assert snap.used_inputs.prompt == 0.5
    assert snap.used_inputs.selection == 0.3
    assert snap.used_inputs.written_context == 0.2


async def test_snapshot_weights_selection_and_written():
    """只有 selection + written_context → selection=0.7, written=0.3"""
    req = AskRequest(session_id="s1", prompt="", selection="选中文本")
    snap = build_snapshot(req, {"draft": "草稿"}, [], "")
    assert snap.used_inputs.prompt == 0.0
    assert snap.used_inputs.selection == 0.7
    assert snap.used_inputs.written_context == 0.3


async def test_snapshot_weights_written_only():
    """只有 written_context → written=1.0"""
    req = AskRequest(session_id="s1", prompt="")
    snap = build_snapshot(req, {"draft": "草稿"}, [], "")
    assert snap.used_inputs.prompt == 0.0
    assert snap.used_inputs.selection == 0.0
    assert snap.used_inputs.written_context == 1.0


# ── snapshot 冻结隔离 ────────────────────────────────────────────────


async def test_snapshot_freeze_isolation():
    """冻结后修改 editor_context 不影响 snapshot"""
    req = AskRequest(session_id="s1", prompt="hello")
    ctx = {"draft": "原始草稿"}
    snap = build_snapshot(req, ctx, [], "")
    ctx["draft"] = "修改后"
    assert snap.written_context == "原始草稿"


async def test_snapshot_freeze_editor_context_none():
    """editor_context=None → written_context 为空字符串"""
    req = AskRequest(session_id="s1", prompt="hello")
    snap = build_snapshot(req, None, [], "")
    assert snap.written_context == ""


async def test_snapshot_preserves_paper_ids():
    """paper_ids 被正确冻结到 snapshot"""
    req = AskRequest(session_id="s1", prompt="hello", paper_ids=["a", "b", "c"])
    snap = build_snapshot(req, None, [], "")
    assert snap.paper_ids == ["a", "b", "c"]


async def test_snapshot_empty_paper_ids_becomes_list():
    """paper_ids=None → 空列表（不是 None）"""
    req = AskRequest(session_id="s1", prompt="hello", paper_ids=None)
    snap = build_snapshot(req, None, [], "")
    assert snap.paper_ids == []
    assert isinstance(snap.paper_ids, list)
