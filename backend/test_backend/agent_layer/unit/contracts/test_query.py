from __future__ import annotations

from datetime import datetime, timezone

from app.agent_layer.contracts.query import AskRequest, FrozenTurnSnapshot
from app.agent_layer.contracts.used_inputs import UsedInputs


class TestAskRequest:
    def test_full_payload(self):
        req = AskRequest(
            session_id="sess-1",
            prompt="你好",
            selection="选中的文本",
            draft="草稿内容",
            paper_ids=["p1", "p2"],
            enable_rag=True,
            model="kimi",
            thinking=True,
        )
        assert req.session_id == "sess-1"
        assert req.prompt == "你好"
        assert req.selection == "选中的文本"
        assert req.draft == "草稿内容"
        assert req.paper_ids == ["p1", "p2"]
        assert req.enable_rag is True
        assert req.model == "kimi"
        assert req.thinking is True

    def test_minimal_payload(self):
        req = AskRequest(session_id="s1", prompt="hi")
        assert req.session_id == "s1"
        assert req.prompt == "hi"
        assert req.selection is None
        assert req.draft is None
        assert req.paper_ids is None
        assert req.enable_rag is True
        assert req.model is None
        assert req.thinking is False

    def test_optional_fields_default(self):
        req = AskRequest(session_id="s", prompt="q")
        assert req.selection is None
        assert req.draft is None
        assert req.paper_ids is None
        assert req.enable_rag is True
        assert req.model is None
        assert req.thinking is False

    def test_from_dict(self):
        data = {"session_id": "s1", "prompt": "hello"}
        req = AskRequest.model_validate(data)
        assert req.session_id == "s1"
        assert req.prompt == "hello"


class TestFrozenTurnSnapshot:
    def test_create(self):
        now = datetime.now(timezone.utc)
        snap = FrozenTurnSnapshot(
            request_id="r1",
            session_id="s1",
            prompt="q",
            selection="sel",
            written_context="ctx",
            paper_ids=["p1"],
            enable_rag=True,
            model_name="kimi",
            thinking_enabled=False,
            recent_window=[],
            history_summary="",
            frozen_at=now,
            used_inputs=UsedInputs(prompt=1.0),
        )
        assert snap.request_id == "r1"
        assert snap.frozen_at == now
        assert snap.used_inputs.prompt == 1.0

    def test_frozen_at_auto_fill(self):
        snap = FrozenTurnSnapshot(
            request_id="r1",
            session_id="s1",
            prompt="q",
            selection="",
            written_context="",
            paper_ids=[],
            enable_rag=True,
            model_name="",
            thinking_enabled=False,
            recent_window=[],
            history_summary="",
            used_inputs=UsedInputs(),
        )
        assert isinstance(snap.frozen_at, datetime)

    def test_used_inputs_defaults(self):
        ui = UsedInputs()
        assert ui.prompt == 0.0
        assert ui.selection == 0.0
        assert ui.written_context == 0.0
        assert ui.rag_evidence == 0.0
