"""TurnRunner 状态机测试"""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _FakeRequest:
    def __init__(self, session_id: str = "s1", prompt: str = "hello", **kw):
        self.session_id = session_id
        self.prompt = prompt
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeUsedInputs:
    def __init__(self):
        self.prompt = 1.0
        self.selection = 0.0
        self.written_context = 0.0

    def model_dump(self):
        return {"prompt": self.prompt, "selection": self.selection, "written_context": self.written_context}


class _FakeSnapshot:
    def __init__(self, **kw):
        self.request_id = "r1"
        self.session_id = kw.get("session_id", "s1")
        self.prompt = kw.get("prompt", "hello")
        self.selection = kw.get("selection", "")
        self.written_context = kw.get("written_context", "")
        self.paper_ids = kw.get("paper_ids", None)
        self.enable_rag = kw.get("enable_rag", False)
        self.model_name = kw.get("model_name", "test")
        self.thinking_enabled = kw.get("thinking_enabled", True)
        self.reflection_enabled = kw.get("reflection_enabled", False)
        self.recent_window = []
        self.history_summary = ""
        self.frozen_at = "2025-01-01T00:00:00Z"
        self.used_inputs = _FakeUsedInputs()


class _FakeEvent:
    def __init__(self, tag: str, **kw):
        self._tag = tag
        self._data = kw

    def to_sse_frame(self) -> str:
        return f"event: {self._tag}\ndata: {self._data}\n\n"

    def model_dump(self) -> dict:
        return {"tag": self._tag, **self._data}


class _FakeSourceCard:
    def __init__(self, **kw):
        self._data = kw

    def model_dump(self) -> dict:
        return self._data


def _install_mocks():
    mods: dict[str, types.ModuleType] = {}

    query_mod = types.ModuleType("app.agent_layer.contracts.query")
    query_mod.AskRequest = _FakeRequest
    query_mod.FrozenTurnSnapshot = _FakeSnapshot
    mods["app.agent_layer.contracts.query"] = query_mod

    sse_mod = types.ModuleType("app.agent_layer.contracts.sse_events")

    def _make_event(tag):
        def factory(**kw):
            return _FakeEvent(tag, **kw)
        return factory

    sse_mod.ThinkingEvent = _make_event("thinking")
    sse_mod.BlockEvent = _make_event("block")
    sse_mod.SourcesEvent = _make_event("sources")
    sse_mod.DoneEvent = _make_event("done")
    sse_mod.ErrorEvent = _make_event("error")
    sse_mod.ReflectionEvent = _make_event("reflection")
    sse_mod.MetadataEvent = _make_event("metadata")
    mods["app.agent_layer.contracts.sse_events"] = sse_mod

    # Mock hooks.reflection
    reflection_mod = types.ModuleType("app.agent_layer.hooks.reflection")

    async def _fake_reflect(chat_model, original_query, llm_output, context="", max_rounds=3):
        from dataclasses import dataclass, field

        @dataclass(frozen=True)
        class _RR:
            output: str
            rounds_used: int
            direction_switches: int
            feedback_log: list = field(default_factory=list)

        return _RR(output=llm_output, rounds_used=0, direction_switches=0)

    reflection_mod.reflect = _fake_reflect
    mods["app.agent_layer.hooks.reflection"] = reflection_mod

    # Mock orchestration.tool_loop
    tool_loop_mod = types.ModuleType("app.agent_layer.orchestration.tool_loop")
    tool_loop_mod.ToolLoopEvent = _make_event("tool_round")

    class _FakeToolRegistry:
        def __init__(self):
            pass

    tool_loop_mod.ToolRegistry = _FakeToolRegistry

    async def _fake_execute(*args, **kwargs):
        pass

    tool_loop_mod.execute_tool_loop = _fake_execute
    mods["app.agent_layer.orchestration.tool_loop"] = tool_loop_mod

    for name, mod in mods.items():
        sys.modules[name] = mod


@pytest.fixture(autouse=True)
def _patch_modules():
    """Install fake modules for turn_runner imports, restore after each test."""
    targets = [
        "app.agent_layer.contracts.query",
        "app.agent_layer.contracts.sse_events",
        "app.agent_layer.hooks.reflection",
        "app.agent_layer.orchestration.tool_loop",
        "app.agent_layer.orchestration.turn_runner",
    ]
    original = {k: sys.modules.get(k) for k in targets}
    for k in targets:
        sys.modules.pop(k, None)
    _install_mocks()
    yield
    for k in targets:
        sys.modules.pop(k, None)
        if original[k] is not None:
            sys.modules[k] = original[k]


@pytest.fixture
def mock_chat_model():
    model = AsyncMock()

    async def _stream(msgs, model=None):
        yield "chunk1"
        yield "chunk2"

    model.chat_stream = _stream
    return model


@pytest.fixture
def mock_window_store():
    store = AsyncMock()
    store.get_messages = AsyncMock(return_value=[])
    store.add_message = AsyncMock()
    return store


@pytest.fixture
def mock_editor_context_store():
    store = AsyncMock()
    store.get = AsyncMock(return_value=None)
    return store


@pytest.fixture
def mock_persistence():
    persistence = AsyncMock()
    persistence.get_summary = AsyncMock(return_value="")
    persistence.save_message = AsyncMock()
    return persistence


@pytest.fixture
def mock_snapshot_builder():
    def builder(request, editor_context, recent_window, history_summary):
        return _FakeSnapshot(
            session_id=request.session_id,
            prompt=request.prompt,
            selection=getattr(request, "selection", ""),
            written_context=getattr(request, "written_context", ""),
            enable_rag=getattr(request, "enable_rag", False),
            thinking_enabled=getattr(request, "thinking", True),
            reflection_enabled=getattr(request, "reflection", False),
        )
    return MagicMock(side_effect=builder)


@pytest.fixture
def mock_retrieval_gate():
    return MagicMock(return_value=False)


@pytest.fixture
def mock_source_mapper():
    return MagicMock(return_value=[])


@pytest.fixture
def mock_block_streamer():
    return MagicMock(return_value=[])


@pytest.fixture
def runner(
    mock_chat_model,
    mock_snapshot_builder,
    mock_retrieval_gate,
    mock_source_mapper,
    mock_block_streamer,
    mock_window_store,
    mock_editor_context_store,
    mock_persistence,
):
    from app.agent_layer.orchestration.turn_runner import TurnRunner

    return TurnRunner(
        chat_model=mock_chat_model,
        snapshot_builder=mock_snapshot_builder,
        retrieval_gate=mock_retrieval_gate,
        source_mapper=mock_source_mapper,
        block_streamer=mock_block_streamer,
        window_store=mock_window_store,
        editor_context_store=mock_editor_context_store,
        persistence=mock_persistence,
    )


async def _collect(runner, request):
    return [frame async for frame in runner.run(request)]


@pytest.mark.asyncio
async def test_basic_flow_no_rag(runner, mock_retrieval_gate, mock_block_streamer):
    mock_retrieval_gate.return_value = False
    mock_block_streamer.return_value = [
        _FakeEvent("block", content="b1"),
        _FakeEvent("block", content="b2"),
    ]

    frames = await _collect(runner, _FakeRequest(prompt="test"))

    event_types = [f.split("\n")[0].split(": ")[1] for f in frames]
    assert event_types == ["metadata", "thinking", "block", "block", "sources", "done"]


@pytest.mark.asyncio
async def test_flow_with_rag(runner, mock_retrieval_gate, mock_source_mapper, mock_block_streamer):
    mock_retrieval_gate.return_value = True
    mock_source_mapper.return_value = [_FakeSourceCard(id="1")]
    mock_block_streamer.return_value = [_FakeEvent("block", content="b1")]

    with patch("app.agent_layer.orchestration.turn_runner.TurnRunner._retrieve", new_callable=AsyncMock) as mock_retrieve:
        mock_retrieve.return_value = [{"content": "doc1"}]
        frames = await _collect(runner, _FakeRequest(prompt="test"))

    event_types = [f.split("\n")[0].split(": ")[1] for f in frames]
    assert event_types == ["metadata", "thinking", "block", "sources", "done"]
    mock_retrieve.assert_called_once()


@pytest.mark.asyncio
async def test_empty_query_yields_error(runner):
    frames = await _collect(runner, _FakeRequest(prompt=""))

    assert len(frames) == 1
    assert "error" in frames[0]


@pytest.mark.asyncio
async def test_llm_exception_yields_error(runner, mock_chat_model):
    async def _fail(msgs, model=None):
        raise RuntimeError("LLM down")
        yield

    mock_chat_model.chat_stream = _fail

    frames = await _collect(runner, _FakeRequest(prompt="test", thinking=False))

    # metadata 在 LLM 调用之前发送，所以异常时有 2 个帧
    assert len(frames) == 2
    assert "metadata" in frames[0]
    assert "error" in frames[1]


@pytest.mark.asyncio
async def test_sse_event_order(runner, mock_retrieval_gate, mock_block_streamer):
    mock_retrieval_gate.return_value = False
    mock_block_streamer.return_value = [
        _FakeEvent("block", content="b1"),
    ]

    frames = await _collect(runner, _FakeRequest(prompt="test"))

    event_types = [f.split("\n")[0].split(": ")[1] for f in frames]

    thinking_idx = event_types.index("thinking")
    block_idx = event_types.index("block")
    sources_idx = event_types.index("sources")
    done_idx = event_types.index("done")

    assert thinking_idx < block_idx
    assert block_idx < sources_idx
    assert sources_idx < done_idx


# ── Reflection 集成测试 ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_reflection_disabled_by_default(runner, mock_block_streamer):
    """reflection_enabled=False 时跳过 reflection"""
    mock_block_streamer.return_value = [_FakeEvent("block", content="b1")]

    frames = await _collect(runner, _FakeRequest(prompt="test"))

    event_types = [f.split("\n")[0].split(": ")[1] for f in frames]
    assert "reflection" not in event_types
    assert "block" in event_types


@pytest.mark.asyncio
async def test_reflection_yields_events(runner, mock_block_streamer):
    """reflection_enabled=True 时产出 reflection 事件"""
    from dataclasses import dataclass, field

    @dataclass(frozen=True)
    class _RR:
        output: str
        rounds_used: int
        direction_switches: int
        feedback_log: list = field(default_factory=list)

    async def _reflect_with_feedback(chat_model, original_query, llm_output, context="", max_rounds=3):
        return _RR(
            output="refined output",
            rounds_used=1,
            direction_switches=0,
            feedback_log=[{"round": 1, "verdict": "supported", "reason": "ok"}],
        )

    # Patch reflect via the turn_runner module's namespace
    import app.agent_layer.orchestration.turn_runner as tr_mod
    tr_mod.reflect = _reflect_with_feedback

    mock_block_streamer.return_value = [_FakeEvent("block", content="b1")]

    frames = await _collect(runner, _FakeRequest(prompt="test", reflection=True))

    event_types = [f.split("\n")[0].split(": ")[1] for f in frames]
    # Should have reflection event before blocks
    assert "reflection" in event_types
    assert "block" in event_types
