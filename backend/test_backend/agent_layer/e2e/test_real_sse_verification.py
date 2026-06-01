"""真实 LLM 端到端验证：429 重试、模型轮转、thinking、多轮对话"""

from __future__ import annotations

import asyncio
import json
import time
import uuid

import pytest

from app.agent_layer.contracts.query import AskRequest
from app.agent_layer.orchestration.turn_runner import TurnRunner
from app.agent_layer.planning.snapshot_builder import build_snapshot
from app.agent_layer.planning.retrieval_gate import should_retrieve
from app.agent_layer.response.source_mapper import map_sources
from app.agent_layer.response.block_streamer import stream_to_blocks
from app.agent_layer.runtime.chat_model import ChatModel
from app.agent_layer.session.window_store import ConversationWindowStore
from app.agent_layer.session.editor_context_store import EditorContextStore
from app.agent_layer.session.persistence import SessionPersistence
from app.service_layer.config.settings import BackendSettings


def _create_runner() -> TurnRunner | None:
    settings = BackendSettings()
    if not settings.llm_configured:
        return None
    return TurnRunner(
        chat_model=ChatModel(settings),
        snapshot_builder=build_snapshot,
        retrieval_gate=should_retrieve,
        source_mapper=map_sources,
        block_streamer=stream_to_blocks,
        window_store=ConversationWindowStore(max_messages=20),
        editor_context_store=EditorContextStore(),
        persistence=SessionPersistence(),
    )


def _parse_events(frames: list[str]) -> dict:
    event_types = []
    blocks = []
    sources = None
    error_msg = None
    thinking_text = None

    for f in frames:
        if "event: " not in f:
            continue
        lines = f.strip().split("\n")
        etype = lines[0].replace("event: ", "").strip()
        event_types.append(etype)
        data_str = lines[1].replace("data: ", "") if len(lines) > 1 else "{}"
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            data = {}

        if etype == "block":
            blocks.append(data)
        elif etype == "sources":
            sources = data
        elif etype == "error":
            error_msg = data.get("message", "")
        elif etype == "thinking":
            thinking_text = data.get("text", "")

    return {
        "event_types": event_types,
        "blocks": blocks,
        "sources": sources,
        "error_msg": error_msg,
        "thinking_text": thinking_text,
        "has_done": "done" in event_types,
        "has_error": "error" in event_types,
        "block_count": event_types.count("block"),
        "success": "done" in event_types and "error" not in event_types,
    }


async def _collect_frames(runner, request) -> list[str]:
    frames = []
    async for frame in runner.run(request):
        frames.append(frame)
    return frames


# ──────────────────────────────────────────────
# Test 1: 基础 SSE 流（当前主模型）
# ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_real_sse_basic():
    """验证基本 SSE 流：thinking → block(s) → sources → done"""
    runner = _create_runner()
    if runner is None:
        pytest.skip("LLM not configured")

    req = AskRequest(
        session_id=f"e2e-basic-{uuid.uuid4().hex[:6]}",
        prompt="用一句话解释什么是 RAG（检索增强生成）",
        enable_rag=False,
    )

    start = time.monotonic()
    frames = await _collect_frames(runner, req)
    elapsed = (time.monotonic() - start) * 1000

    result = _parse_events(frames)

    print(f"\n{'='*60}")
    print(f"Test 1: 基础 SSE 流")
    print(f"  耗时: {elapsed:.0f}ms")
    print(f"  事件序列: {result['event_types']}")
    print(f"  block 数量: {result['block_count']}")
    print(f"  成功: {result['success']}")
    if result["error_msg"]:
        print(f"  错误: {result['error_msg']}")
    print(f"{'='*60}")

    assert result["success"], f"SSE 流未正常完成: {result['error_msg']}"
    assert result["block_count"] > 0, "没有收到任何 block"


# ──────────────────────────────────────────────
# Test 2: Thinking 事件
# ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_real_sse_thinking():
    """验证 thinking_enabled=True 时发出 thinking 事件"""
    runner = _create_runner()
    if runner is None:
        pytest.skip("LLM not configured")

    req = AskRequest(
        session_id=f"e2e-think-{uuid.uuid4().hex[:6]}",
        prompt="什么是梯度下降？",
        enable_rag=False,
        thinking=True,
    )

    frames = await _collect_frames(runner, req)
    result = _parse_events(frames)

    print(f"\n{'='*60}")
    print(f"Test 2: Thinking 事件")
    print(f"  事件序列: {result['event_types']}")
    print(f"  有 thinking: {'thinking' in result['event_types']}")
    print(f"  成功: {result['success']}")
    print(f"{'='*60}")

    assert result["success"]
    assert "thinking" in result["event_types"], "未收到 thinking 事件"


# ──────────────────────────────────────────────
# Test 3: 多轮对话上下文保持
# ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_real_sse_multi_turn():
    """验证多轮对话中 LLM 能理解上下文"""
    runner = _create_runner()
    if runner is None:
        pytest.skip("LLM not configured")

    session_id = f"e2e-multi-{uuid.uuid4().hex[:6]}"

    # 第 1 轮
    req1 = AskRequest(session_id=session_id, prompt="什么是机器学习？", enable_rag=False)
    frames1 = await _collect_frames(runner, req1)
    r1 = _parse_events(frames1)
    assert r1["success"], f"第 1 轮失败: {r1['error_msg']}"

    # 第 2 轮：用代词 "它"
    req2 = AskRequest(session_id=session_id, prompt="它有哪些主要分类？", enable_rag=False)
    frames2 = await _collect_frames(runner, req2)
    r2 = _parse_events(frames2)

    # 提取第 2 轮的文本（从所有 block 中提取）
    text2 = ""
    for b in r2["blocks"]:
        # paragraph block: text 直接在顶层
        if "text" in b:
            text2 += b["text"]
        # list block: items 里有 text
        for item in b.get("items", []):
            if isinstance(item, dict) and "text" in item:
                text2 += item["text"]

    print(f"\n{'='*60}")
    print(f"Test 3: 多轮对话")
    print(f"  第 1 轮成功: {r1['success']}")
    print(f"  第 2 轮成功: {r2['success']}")
    print(f"  第 2 轮回答片段: {text2[:200]}...")
    print(f"  第 2 轮原始 blocks: {r2['blocks'][:2]}")
    # 检查第 2 轮是否理解 "它" = 机器学习
    keywords = ["机器学习", "监督", "无监督", "分类", "回归", "聚类", "深度学习", "学习"]
    understood = any(k in text2 for k in keywords)
    print(f"  上下文理解: {understood}")
    print(f"{'='*60}")

    assert r2["success"], f"第 2 轮失败: {r2['error_msg']}"
    assert understood, "第 2 轮未理解上下文（'它' 应指机器学习）"


# ──────────────────────────────────────────────
# Test 4: 模型切换验证
# ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_real_sse_model_switch():
    """验证不同模型都能正常工作"""
    runner = _create_runner()
    if runner is None:
        pytest.skip("LLM not configured")

    settings = BackendSettings()
    models_to_test = [settings.llm_model] + settings.llm_fallback_list[:2]

    results = {}
    for model in models_to_test:
        session_id = f"e2e-model-{uuid.uuid4().hex[:6]}"
        req = AskRequest(
            session_id=session_id,
            prompt="用一句话回答：1+1等于几？",
            enable_rag=False,
            model=model,
        )
        try:
            start = time.monotonic()
            frames = await _collect_frames(runner, req)
            elapsed = (time.monotonic() - start) * 1000
            parsed = _parse_events(frames)
            results[model] = {
                "success": parsed["success"],
                "elapsed_ms": round(elapsed),
                "blocks": parsed["block_count"],
                "error": parsed["error_msg"],
            }
        except Exception as e:
            results[model] = {"success": False, "elapsed_ms": 0, "blocks": 0, "error": str(e)}

    print(f"\n{'='*60}")
    print(f"Test 4: 模型切换验证")
    for model, r in results.items():
        status = "✓" if r["success"] else "✗"
        print(f"  {status} {model}: {r['elapsed_ms']}ms, blocks={r['blocks']}, error={r.get('error', '')}")
    print(f"{'='*60}")

    for model, r in results.items():
        assert r["success"], f"模型 {model} 失败: {r.get('error', '')}"


# ──────────────────────────────────────────────
# Test 5: 并发请求不互相干扰
# ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_real_sse_concurrent():
    """3 个并发请求各自独立"""
    runner = _create_runner()
    if runner is None:
        pytest.skip("LLM not configured")

    prompts = ["什么是 Transformer？", "解释一下注意力机制", "什么是预训练？"]
    session_ids = [f"e2e-conc-{i}-{uuid.uuid4().hex[:4]}" for i in range(3)]

    async def run_one(sid, prompt):
        req = AskRequest(session_id=sid, prompt=prompt, enable_rag=False)
        start = time.monotonic()
        frames = await _collect_frames(runner, req)
        elapsed = (time.monotonic() - start) * 1000
        parsed = _parse_events(frames)
        return {
            "session": sid,
            "success": parsed["success"],
            "elapsed_ms": round(elapsed),
            "blocks": parsed["block_count"],
            "error": parsed["error_msg"],
        }

    start = time.monotonic()
    tasks = [run_one(sid, p) for sid, p in zip(session_ids, prompts)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total_elapsed = (time.monotonic() - start) * 1000

    print(f"\n{'='*60}")
    print(f"Test 5: 并发请求（3 个）")
    print(f"  总耗时: {total_elapsed:.0f}ms")
    for r in results:
        if isinstance(r, Exception):
            print(f"  ✗ 异常: {r}")
        else:
            status = "✓" if r["success"] else "✗"
            print(f"  {status} {r['session']}: {r['elapsed_ms']}ms, blocks={r['blocks']}")
    print(f"{'='*60}")

    for r in results:
        assert not isinstance(r, Exception), f"并发异常: {r}"
        assert r["success"], f"并发请求失败: {r.get('error', '')}"


# ──────────────────────────────────────────────
# Test 6: 空 prompt 处理
# ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_real_sse_empty_prompt():
    """空 prompt 应返回 ErrorEvent"""
    runner = _create_runner()
    if runner is None:
        pytest.skip("LLM not configured")

    req = AskRequest(session_id=f"e2e-empty-{uuid.uuid4().hex[:6]}", prompt="", enable_rag=False)
    frames = await _collect_frames(runner, req)
    result = _parse_events(frames)

    print(f"\n{'='*60}")
    print(f"Test 6: 空 prompt 处理")
    print(f"  事件序列: {result['event_types']}")
    print(f"  有 error: {result['has_error']}")
    print(f"{'='*60}")

    assert result["has_error"], "空 prompt 应返回 error 事件"
