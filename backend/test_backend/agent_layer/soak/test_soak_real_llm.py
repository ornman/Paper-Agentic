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

from .soak_config import SoakConfig, ALL_PROMPTS, get_soak_config
from .soak_reporter import SoakCollector, SoakHealthChecker, RequestMetrics


def _create_real_runner() -> TurnRunner | None:
    """创建真实 LLM runner，如果配置不可用返回 None"""
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


async def _run_single_request(runner, session_id, prompt, collector, thinking=False):
    """同 mock 版本的 _run_single_request"""
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
                etype = f.split("event: ")[1].split("\n")[0]
                event_types.append(etype)

        metrics.event_types = event_types
        metrics.success = "done" in event_types
        metrics.block_count = event_types.count("block")
        metrics.source_count = 1 if "sources" in event_types else 0
        metrics.has_thinking = "thinking" in event_types

        if "error" in event_types and "done" not in event_types:
            for f in frames:
                if "event: error" in f:
                    data = json.loads(f.split("data: ")[1])
                    metrics.error_message = data.get("message", "")
                    break

    except Exception as e:
        metrics.finished_at = time.monotonic()
        metrics.response_time_ms = (metrics.finished_at - metrics.started_at) * 1000
        metrics.success = False
        metrics.error_message = str(e)

    collector.record(metrics)
    return metrics


@pytest.mark.asyncio
async def test_soak_real_llm_30min():
    """真实 LLM 30 分钟浸泡测试"""
    runner = _create_real_runner()
    if runner is None:
        pytest.skip("LLM not configured")

    config = get_soak_config(
        duration_seconds=1800,  # 30 分钟
        request_interval_seconds=15,
    )

    collector = SoakCollector()
    health = SoakHealthChecker(config)
    collector.start()

    session_id = f"soak-real-{int(time.time())}"
    start = time.monotonic()

    while time.monotonic() - start < config.duration_seconds:
        prompt = random.choice(ALL_PROMPTS)
        if not prompt:
            prompt = "你好"
        thinking = random.random() < 0.3  # 30% 请求启用 thinking

        metrics = await _run_single_request(runner, session_id, prompt, collector, thinking=thinking)

        if not health.check(metrics):
            break

        await asyncio.sleep(config.request_interval_seconds)

    report = collector.generate_report()

    report_path = f"{config.report_dir}/real_soak_30min_{int(time.time())}.json"
    collector.save_report(report, report_path)

    assert report.total_requests > 0
    assert report.success_rate >= 0.8


@pytest.mark.asyncio
async def test_soak_real_llm_2hr():
    """真实 LLM 2 小时浸泡测试"""
    runner = _create_real_runner()
    if runner is None:
        pytest.skip("LLM not configured")

    config = get_soak_config(
        duration_seconds=7200,  # 2 小时
        request_interval_seconds=30,
    )

    collector = SoakCollector()
    health = SoakHealthChecker(config)
    collector.start()

    session_id = f"soak-real-2h-{int(time.time())}"
    start = time.monotonic()

    while time.monotonic() - start < config.duration_seconds:
        prompt = random.choice(ALL_PROMPTS)
        if not prompt:
            prompt = "你好"
        thinking = random.random() < 0.3

        metrics = await _run_single_request(runner, session_id, prompt, collector, thinking=thinking)

        if not health.check(metrics):
            break

        await asyncio.sleep(config.request_interval_seconds)

    report = collector.generate_report()

    report_path = f"{config.report_dir}/real_soak_2hr_{int(time.time())}.json"
    collector.save_report(report, report_path)

    assert report.total_requests > 0
