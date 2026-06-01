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
from app.agent_layer.session.window_store import ConversationWindowStore
from app.agent_layer.session.editor_context_store import EditorContextStore
from app.agent_layer.session.persistence import SessionPersistence

from .soak_config import SoakConfig, ALL_PROMPTS, get_soak_config
from .soak_reporter import SoakCollector, SoakHealthChecker, RequestMetrics


class MockChatModel:
    """可配置故障注入的 mock LLM"""

    def __init__(self, fault_rate: float = 0.0):
        self._fault_rate = fault_rate
        self._call_count = 0

    async def chat_stream(self, messages, model=None):
        self._call_count += 1
        if random.random() < self._fault_rate:
            raise RuntimeError("Mock LLM fault injection")

        response = "这是第{}轮的模拟回答。根据相关研究，该方法在多个场景下表现良好。".format(self._call_count)
        for i in range(0, len(response), 20):
            yield response[i:i+20]
            await asyncio.sleep(0.01)  # 模拟流式延迟


def _create_runner(fault_rate: float = 0.0) -> TurnRunner:
    return TurnRunner(
        chat_model=MockChatModel(fault_rate=fault_rate),
        snapshot_builder=build_snapshot,
        retrieval_gate=should_retrieve,
        source_mapper=map_sources,
        block_streamer=stream_to_blocks,
        window_store=ConversationWindowStore(max_messages=20),
        editor_context_store=EditorContextStore(),
        persistence=SessionPersistence(),
    )


async def _run_single_request(
    runner: TurnRunner,
    session_id: str,
    prompt: str,
    collector: SoakCollector,
):
    req = AskRequest(session_id=session_id, prompt=prompt, enable_rag=False)
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
async def test_soak_mock_llm_short():
    """短时间浸泡测试：mock LLM，无故障，60 秒"""
    config = get_soak_config(
        duration_seconds=60,
        request_interval_seconds=2.0,
        fault_injection_rate=0.0,
    )

    runner = _create_runner(fault_rate=0.0)
    collector = SoakCollector()
    health = SoakHealthChecker(config)
    collector.start()

    session_id = "soak-test-001"
    start = time.monotonic()
    request_count = 0

    while time.monotonic() - start < config.duration_seconds:
        prompt = random.choice(ALL_PROMPTS[:20])  # 只用前 20 个
        if not prompt:
            prompt = "test"

        metrics = await _run_single_request(runner, session_id, prompt, collector)
        request_count += 1

        if not health.check(metrics):
            break

        await asyncio.sleep(config.request_interval_seconds)

    report = collector.generate_report()

    # 断言
    assert report.total_requests > 0
    assert report.success_rate >= 0.9
    assert report.avg_response_time_ms < 10000

    # 保存报告
    report_path = f"{config.report_dir}/mock_soak_short_{int(time.time())}.json"
    collector.save_report(report, report_path)


@pytest.mark.asyncio
async def test_soak_mock_llm_with_faults():
    """故障注入浸泡测试：10% 故障率，60 秒"""
    config = get_soak_config(
        duration_seconds=60,
        request_interval_seconds=2.0,
        fault_injection_rate=0.1,
    )

    runner = _create_runner(fault_rate=0.1)
    collector = SoakCollector()
    health = SoakHealthChecker(config)
    collector.start()

    session_id = "soak-fault-001"
    start = time.monotonic()

    while time.monotonic() - start < config.duration_seconds:
        prompt = random.choice(ALL_PROMPTS[:20])
        if not prompt:
            prompt = "test"

        metrics = await _run_single_request(runner, session_id, prompt, collector)

        if not health.check(metrics):
            break

        await asyncio.sleep(config.request_interval_seconds)

    report = collector.generate_report()

    # 有故障注入时，成功率应该降低但不能太低
    assert report.total_requests > 0
    assert report.failed_requests > 0  # 应该有失败
    assert report.success_rate >= 0.5  # 但不能太低

    report_path = f"{config.report_dir}/mock_soak_fault_{int(time.time())}.json"
    collector.save_report(report, report_path)


@pytest.mark.asyncio
async def test_soak_multi_session():
    """多 session 并发浸泡测试：5 个 session，60 秒"""
    config = get_soak_config(
        duration_seconds=60,
        request_interval_seconds=3.0,
        concurrent_sessions=5,
    )

    runners = [_create_runner(fault_rate=0.0) for _ in range(config.concurrent_sessions)]
    collector = SoakCollector()
    collector.start()

    start = time.monotonic()

    async def session_loop(session_idx: int, runner: TurnRunner):
        session_id = f"soak-multi-{session_idx}"
        while time.monotonic() - start < config.duration_seconds:
            prompt = random.choice(ALL_PROMPTS[:20])
            if not prompt:
                prompt = "test"
            await _run_single_request(runner, session_id, prompt, collector)
            await asyncio.sleep(config.request_interval_seconds)

    await asyncio.gather(*[session_loop(i, r) for i, r in enumerate(runners)])

    report = collector.generate_report()

    assert report.total_requests > 0
    assert report.success_rate >= 0.95

    # 验证 session 隔离
    sessions_seen = set(r.session_id for r in collector._requests)
    assert len(sessions_seen) == config.concurrent_sessions

    report_path = f"{config.report_dir}/mock_soak_multi_{int(time.time())}.json"
    collector.save_report(report, report_path)
