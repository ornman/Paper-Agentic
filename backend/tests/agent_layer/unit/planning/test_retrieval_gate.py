from __future__ import annotations

from datetime import datetime, timezone

from app.agent_layer.contracts.query import FrozenTurnSnapshot
from app.agent_layer.contracts.used_inputs import UsedInputs
from app.agent_layer.planning.retrieval_gate import should_retrieve


def _make_snapshot(**kwargs):
    defaults = {
        "request_id": "r1",
        "session_id": "s1",
        "prompt": "q",
        "selection": "",
        "written_context": "",
        "paper_ids": [],
        "enable_rag": True,
        "model_name": "",
        "thinking_enabled": False,
        "recent_window": [],
        "history_summary": "",
        "frozen_at": datetime.now(timezone.utc),
        "used_inputs": UsedInputs(prompt=1.0),
    }
    defaults.update(kwargs)
    return FrozenTurnSnapshot(**defaults)


class TestShouldRetrieve:
    def test_rag_disabled(self):
        snap = _make_snapshot(enable_rag=False, paper_ids=["p1"])
        assert should_retrieve(snap) is False

    def test_no_paper_ids_no_selection(self):
        snap = _make_snapshot(enable_rag=True, paper_ids=[], selection="")
        assert should_retrieve(snap) is False

    def test_has_paper_ids(self):
        snap = _make_snapshot(enable_rag=True, paper_ids=["p1"])
        assert should_retrieve(snap) is True

    def test_has_selection(self):
        snap = _make_snapshot(
            enable_rag=True, paper_ids=[], selection="some text"
        )
        assert should_retrieve(snap) is True

    def test_has_both(self):
        snap = _make_snapshot(
            enable_rag=True, paper_ids=["p1"], selection="text"
        )
        assert should_retrieve(snap) is True

    def test_rag_disabled_ignores_paper_ids(self):
        snap = _make_snapshot(
            enable_rag=False, paper_ids=["p1", "p2"], selection="text"
        )
        assert should_retrieve(snap) is False
