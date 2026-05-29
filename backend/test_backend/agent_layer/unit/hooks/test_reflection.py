"""Reflection 循环单元测试"""

from __future__ import annotations

import json

import pytest

from app.agent_layer.hooks.reflection import (
    ReflectionResult,
    _parse_verdict,
    reflect,
)


# ── _parse_verdict ────────────────────────────────────────────────


class TestParseVerdict:
    def test_valid_supported(self):
        raw = json.dumps({"verdict": "supported", "reason": "有据可查", "direction": "refine"})
        verdict, reason, direction = _parse_verdict(raw)
        assert verdict == "supported"
        assert reason == "有据可查"
        assert direction == "refine"

    def test_valid_unsupported(self):
        raw = json.dumps({"verdict": "unsupported", "reason": "缺少引用", "direction": "rephrase"})
        verdict, reason, direction = _parse_verdict(raw)
        assert verdict == "unsupported"
        assert direction == "rephrase"

    def test_invalid_verdict_defaults_unsupported(self):
        raw = json.dumps({"verdict": "maybe", "reason": "模糊", "direction": "refine"})
        verdict, _, _ = _parse_verdict(raw)
        assert verdict == "unsupported"

    def test_invalid_direction_defaults_refine(self):
        raw = json.dumps({"verdict": "unsupported", "reason": "", "direction": "unknown"})
        _, _, direction = _parse_verdict(raw)
        assert direction == "refine"

    def test_malformed_json_with_supported_keyword(self):
        verdict, _, _ = _parse_verdict("this looks supported to me")
        assert verdict == "supported"

    def test_malformed_json_without_supported(self):
        verdict, _, _ = _parse_verdict("complete nonsense")
        assert verdict == "unsupported"

    def test_json_in_code_block(self):
        raw = '```json\n{"verdict": "supported", "reason": "ok", "direction": "refine"}\n```'
        verdict, reason, _ = _parse_verdict(raw)
        assert verdict == "supported"
        assert reason == "ok"


# ── reflect() ─────────────────────────────────────────────────────


class _MockChatModel:
    """可配置的 mock：依次返回预设回复"""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._call_idx = 0
        self.call_messages: list[list[dict]] = []

    async def chat(self, messages: list[dict], model: str | None = None) -> str:
        self.call_messages.append(messages)
        idx = min(self._call_idx, len(self._responses) - 1)
        self._call_idx += 1
        return self._responses[idx]

    async def chat_stream(self, messages: list[dict], model: str | None = None):
        yield await self.chat(messages, model)


@pytest.mark.asyncio
async def test_reflect_supported_first_round():
    """第一轮就 supported，立即停止"""
    model = _MockChatModel([
        json.dumps({"verdict": "supported", "reason": "回答准确", "direction": "refine"}),
    ])
    result = await reflect(model, "什么是 RAG？", "RAG 是检索增强生成", context="RAG 定义...")
    assert result.output == "RAG 是检索增强生成"
    assert result.rounds_used == 1
    assert result.direction_switches == 0
    assert result.feedback_log[0]["verdict"] == "supported"


@pytest.mark.asyncio
async def test_reflect_refine_then_supported():
    """第一轮 unsupported → refine → 第二轮 supported"""
    model = _MockChatModel([
        json.dumps({"verdict": "unsupported", "reason": "缺少引用", "direction": "refine"}),
        "改进后的回答：RAG 是检索增强生成[1]",
        json.dumps({"verdict": "supported", "reason": "已有引用", "direction": "refine"}),
    ])
    result = await reflect(model, "什么是 RAG？", "RAG 是检索增强生成")
    assert result.rounds_used == 2
    assert "改进后的回答" in result.output


@pytest.mark.asyncio
async def test_reflect_max_rounds():
    """达到最大轮数后停止，保留最后的精炼输出"""
    model = _MockChatModel([
        json.dumps({"verdict": "unsupported", "reason": "r1", "direction": "refine"}),
        "v2",
        json.dumps({"verdict": "unsupported", "reason": "r2", "direction": "refine"}),
        "v3",
        json.dumps({"verdict": "unsupported", "reason": "r3", "direction": "refine"}),
        "v4",
    ])
    result = await reflect(model, "q", "a1", max_rounds=3)
    assert result.rounds_used == 3
    # 每轮都执行 refinement，最终输出是 round 3 的精炼结果
    assert result.output == "v4"


@pytest.mark.asyncio
async def test_reflect_direction_switch_limit():
    """2 次方向切换后停止"""
    model = _MockChatModel([
        json.dumps({"verdict": "unsupported", "reason": "r1", "direction": "refine"}),
        "v2",
        json.dumps({"verdict": "unsupported", "reason": "r2", "direction": "rephrase"}),  # switch 1
        "v3",
        json.dumps({"verdict": "unsupported", "reason": "r3", "direction": "refine"}),   # switch 2, stop
    ])
    result = await reflect(model, "q", "a1", max_rounds=5)
    assert result.direction_switches == 2
    assert result.rounds_used == 3


@pytest.mark.asyncio
async def test_reflect_llm_error_stops_gracefully():
    """LLM 调用出错时优雅停止"""
    class _FailModel:
        async def chat(self, messages, model=None):
            raise RuntimeError("LLM down")

    result = await reflect(_FailModel(), "q", "a1")
    assert result.output == "a1"  # 保留原始输出
    assert result.rounds_used == 0


@pytest.mark.asyncio
async def test_reflect_refine_error_keeps_current():
    """refine 阶段出错，保留当前输出"""
    call_count = 0

    class _PartialFail:
        async def chat(self, messages, model=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return json.dumps({"verdict": "unsupported", "reason": "bad", "direction": "refine"})
            raise RuntimeError("refine failed")

    result = await reflect(_PartialFail(), "q", "a1")
    assert result.output == "a1"
    assert result.rounds_used == 1


@pytest.mark.asyncio
async def test_reflect_no_context():
    """无 context 时也能正常工作"""
    model = _MockChatModel([
        json.dumps({"verdict": "supported", "reason": "ok", "direction": "refine"}),
    ])
    result = await reflect(model, "q", "a1", context="")
    assert result.rounds_used == 1
    # 验证 prompt 中包含"无外部资料"
    assert "无外部资料" in model.call_messages[0][0]["content"]
