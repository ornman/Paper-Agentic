"""快速真实 LLM soak 测试（5 分钟）- 验证 429 重试 + 模型轮转"""

from __future__ import annotations

import asyncio
import json
import random
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

from .soak_config import ALL_PROMPTS, get_soak_config
from .soak_reporter import SoakCollector, SoakHealthChecker, RequestMetrics


def _create_real_runner() -> TurnRunner | None:
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


async def _run_one(runner, session_id, prompt, thinking=False):
    req = AskRequest(session_id=session_id, prompt=prompt, enable_rag=False, thinking=thinking)
    metrics = RequestMetrics(
        request_id=uuid.uuid4().hex[:8],
        session_id=session_id,
        prompt_preview=prompt[:50],
        started_at=time.monotonic(),
    )
    try:
        frames = []
        async for frame in runner.run(req):
            frames.append(frame)
        metrics.finished_at = time.monotonic()
        metrics.response_time_ms = (metrics.finished_at - metrics.started_at) * 1000
        event_types = []
        for f in frames:
            if "event: " in f:
                event_types.append(f.split("event: ")[1].split("\n")[0])
        metrics.event_types = event_types
        metrics.success = "done" in event_types
        metrics.block_count = event_types.count("block")
        metrics.has_thinking = "thinking" in event_types
        if "error" in event_types and "done" not in event_types:
            for f in frames:
                if "event: error" in f:
                    try:
                        data = json.loads(f.split("data: ")[1])
                        metrics.error_message = data.get("message", "")
                    except (json.JSONDecodeError, IndexError):
                        pass
                    break
    except Exception as e:
        metrics.finished_at = time.monotonic()
        metrics.response_time_ms = (metrics.finished_at - metrics.started_at) * 1000
        metrics.success = False
        metrics.error_message = str(e)
    return metrics


@pytest.mark.asyncio
async def test_soak_real_5min():
    """真实 LLM 5 分钟 soak 测试：429 重试 + 模型轮转 + thinking 覆盖"""
    runner = _create_real_runner()
    if runner is None:
        pytest.skip("LLM not configured")

    settings = BackendSettings()
    print(f"\n{'='*60}")
    print(f"主模型: {settings.llm_model}")
    print(f"Fallback: {settings.llm_fallback_list}")
    print(f"持续时间: 300s, 请求间隔: 8s")
    print(f"{'='*60}")

    collector = SoakCollector()
    config = get_soak_config(duration_seconds=300, request_interval_seconds=8)
    health = SoakHealthChecker(config)
    collector.start()

    session_id = f"soak-5m-{int(time.time())}"
    start = time.monotonic()
    request_count = 0

    while time.monotonic() - start < 300:
        prompt = random.choice(ALL_PROMPTS) or "你好"
        thinking = random.random() < 0.3

        metrics = await _run_one(runner, session_id, prompt, thinking=thinking)
        collector.record(metrics)
        request_count += 1

        status = "✓" if metrics.success else "✗"
        think_tag = " [thinking]" if metrics.has_thinking else ""
        elapsed = metrics.response_time_ms or 0
        print(
            f"  [{request_count:3d}] {status} {elapsed:6.0f}ms "
            f"blocks={metrics.block_count}{think_tag} "
            f"err={metrics.error_message or '-'}"
        )

        if not health.check(metrics):
            print("  !! 连续失败过多，提前终止")
            break

        await asyncio.sleep(config.request_interval_seconds)

    report = collector.generate_report()
    report_path = f"{config.report_dir}/soak_5min_{int(time.time())}.json"
    collector.save_report(report, report_path)

    print(f"\n{'='*60}")
    print(f"Soak 测试结果")
    print(f"  总请求: {report.total_requests}")
    print(f"  成功: {report.successful_requests}")
    print(f"  失败: {report.failed_requests}")
    print(f"  成功率: {report.success_rate:.1%}")
    print(f"  平均响应: {report.avg_response_time_ms:.0f}ms")
    print(f"  P50: {report.p50_response_time_ms:.0f}ms")
    print(f"  P95: {report.p95_response_time_ms:.0f}ms")
    print(f"  P99: {report.p99_response_time_ms:.0f}ms")
    print(f"  429 错误数: {sum(1 for m in collector._requests if m.error_message and '429' in str(m.error_message))}")
    print(f"  thinking 覆盖: {sum(1 for m in collector._requests if m.has_thinking)}/{report.total_requests}")
    print(f"  报告已保存: {report_path}")
    print(f"{'='*60}")

    assert report.total_requests > 0
    assert report.success_rate >= 0.7, f"成功率过低: {report.success_rate:.1%}"
