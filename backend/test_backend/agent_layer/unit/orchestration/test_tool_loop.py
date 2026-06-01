"""Tool Loop 单元测试"""

from __future__ import annotations

import json

import pytest

from app.agent_layer.orchestration.tool_loop import (
    ToolCall,
    ToolLoopEvent,
    ToolLoopResult,
    ToolRegistry,
    ToolResult,
    execute_tool_loop,
)


# ── ToolRegistry ──────────────────────────────────────────────────


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        async def my_tool(args): return "ok"
        reg.register("t1", my_tool)
        assert reg.has("t1")
        assert reg.get("t1") is my_tool

    def test_get_missing(self):
        reg = ToolRegistry()
        assert reg.get("nope") is None
        assert not reg.has("nope")

    def test_tool_names(self):
        reg = ToolRegistry()
        async def a(args): return None
        async def b(args): return None
        reg.register("a", a)
        reg.register("b", b)
        assert set(reg.tool_names) == {"a", "b"}


# ── ToolLoopEvent ─────────────────────────────────────────────────


class TestToolLoopEvent:
    def test_sse_frame(self):
        event = ToolLoopEvent(round=1, tool_name="search", status="calling")
        frame = event.to_sse_frame()
        assert "event: tool_round" in frame
        data = json.loads(frame.split("data: ")[1].split("\n")[0])
        assert data["round"] == 1
        assert data["tool_name"] == "search"


# ── execute_tool_loop ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tool_loop_no_call():
    """LLM 不调用工具，直接结束"""
    async def decide(msgs):
        return None

    result = await execute_tool_loop(decide, [{"role": "user", "content": "hi"}], ToolRegistry())
    assert result.rounds_used == 0
    assert result.tool_calls == []
    assert not result.hit_max_rounds


@pytest.mark.asyncio
async def test_tool_loop_single_call():
    """单轮工具调用后 LLM 结束"""
    reg = ToolRegistry()
    async def search(args):
        return {"results": [args.get("query", "")]}
    reg.register("search", search)

    call_count = 0
    async def decide(msgs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ToolCall(name="search", arguments={"query": "RAG"})
        return None

    result = await execute_tool_loop(decide, [{"role": "user", "content": "搜索 RAG"}], reg)
    assert result.rounds_used == 1
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "search"
    assert result.tool_results[0].success
    assert not result.hit_max_rounds


@pytest.mark.asyncio
async def test_tool_loop_max_rounds():
    """超过 5 轮硬上限强制停止"""
    reg = ToolRegistry()
    async def noop(args):
        return "ok"
    reg.register("noop", noop)

    async def always_call(msgs):
        return ToolCall(name="noop", arguments={})

    result = await execute_tool_loop(always_call, [], reg, max_rounds=5)
    assert result.rounds_used == 5
    assert result.hit_max_rounds
    assert len(result.tool_calls) == 5
    # 最后一次调用标记为 max rounds
    assert result.tool_results[-1].error == "max rounds reached"


@pytest.mark.asyncio
async def test_tool_loop_tool_not_found():
    """工具不存在时记录错误但继续循环"""
    reg = ToolRegistry()

    call_count = 0
    async def decide(msgs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ToolCall(name="ghost", arguments={})
        return None

    result = await execute_tool_loop(decide, [], reg)
    assert result.rounds_used == 1
    assert not result.tool_results[0].success
    assert "not found" in result.tool_results[0].error


@pytest.mark.asyncio
async def test_tool_loop_tool_exception():
    """工具执行异常时记录错误并继续"""
    reg = ToolRegistry()
    async def fail(args):
        raise ValueError("boom")
    reg.register("fail", fail)

    call_count = 0
    async def decide(msgs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ToolCall(name="fail", arguments={})
        return None

    result = await execute_tool_loop(decide, [], reg)
    assert result.rounds_used == 1
    assert not result.tool_results[0].success
    assert "boom" in result.tool_results[0].error


@pytest.mark.asyncio
async def test_tool_loop_multi_round():
    """多轮工具调用：search → summarize → done"""
    reg = ToolRegistry()
    async def search(args):
        return {"docs": ["doc1", "doc2"]}
    async def summarize(args):
        return {"summary": "这是摘要"}
    reg.register("search", search)
    reg.register("summarize", summarize)

    call_count = 0
    async def decide(msgs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ToolCall(name="search", arguments={"q": "test"})
        if call_count == 2:
            return ToolCall(name="summarize", arguments={"text": "docs"})
        return None

    result = await execute_tool_loop(decide, [], reg)
    assert result.rounds_used == 2
    assert len(result.tool_calls) == 2
    assert result.tool_calls[0].name == "search"
    assert result.tool_calls[1].name == "summarize"
    assert all(r.success for r in result.tool_results)


@pytest.mark.asyncio
async def test_tool_loop_messages_grow():
    """每次工具调用后 messages 列表增长"""
    reg = ToolRegistry()
    async def echo(args):
        return args
    reg.register("echo", echo)

    msgs_seen = []
    call_count = 0
    async def decide(msgs):
        nonlocal call_count
        call_count += 1
        msgs_seen.append(len(msgs))
        if call_count <= 2:
            return ToolCall(name="echo", arguments={"n": call_count})
        return None

    initial = [{"role": "user", "content": "hi"}]
    await execute_tool_loop(decide, initial, reg)
    # 初始 1 条 → +1 tool result → +1 tool result → 每轮增加
    assert msgs_seen[0] == 1
    assert msgs_seen[1] == 2
    assert msgs_seen[2] == 3


@pytest.mark.asyncio
async def test_tool_loop_custom_max_rounds():
    """自定义 max_rounds=2"""
    reg = ToolRegistry()
    async def noop(args):
        return "ok"
    reg.register("noop", noop)

    async def always_call(msgs):
        return ToolCall(name="noop", arguments={})

    result = await execute_tool_loop(always_call, [], reg, max_rounds=2)
    assert result.rounds_used == 2
    assert result.hit_max_rounds
