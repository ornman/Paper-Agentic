from __future__ import annotations

import json
import time
import statistics
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime, timezone


@dataclass
class RequestMetrics:
    request_id: str
    session_id: str
    prompt_preview: str          # 前 50 字
    started_at: float            # time.monotonic
    finished_at: float = 0.0
    success: bool = False
    error_message: str = ""
    event_types: list[str] = field(default_factory=list)
    block_count: int = 0
    source_count: int = 0
    has_thinking: bool = False
    response_time_ms: float = 0.0


@dataclass
class SoakReport:
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    success_rate: float = 0.0

    # 响应时间
    avg_response_time_ms: float = 0.0
    p50_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0
    max_response_time_ms: float = 0.0

    # 错误分布
    error_distribution: dict[str, int] = field(default_factory=dict)

    # SSE 事件统计
    avg_blocks_per_response: float = 0.0
    avg_sources_per_response: float = 0.0
    thinking_usage_rate: float = 0.0

    # 请求详情
    requests: list[dict] = field(default_factory=list)


class SoakCollector:
    def __init__(self):
        self._requests: list[RequestMetrics] = []
        self._start_time: float = 0.0
        self._start_datetime: str = ""

    def start(self):
        self._start_time = time.monotonic()
        self._start_datetime = datetime.now(timezone.utc).isoformat()

    def record(self, metrics: RequestMetrics):
        self._requests.append(metrics)

    def generate_report(self) -> SoakReport:
        if not self._requests:
            return SoakReport()

        elapsed = time.monotonic() - self._start_time
        successful = [r for r in self._requests if r.success]
        failed = [r for r in self._requests if not r.success]
        response_times = [r.response_time_ms for r in self._requests if r.response_time_ms > 0]

        error_dist: dict[str, int] = {}
        for r in failed:
            key = r.error_message[:100] if r.error_message else "unknown"
            error_dist[key] = error_dist.get(key, 0) + 1

        return SoakReport(
            started_at=self._start_datetime,
            finished_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(elapsed, 1),
            total_requests=len(self._requests),
            successful_requests=len(successful),
            failed_requests=len(failed),
            success_rate=round(len(successful) / len(self._requests), 4) if self._requests else 0,
            avg_response_time_ms=round(statistics.mean(response_times), 1) if response_times else 0,
            p50_response_time_ms=round(statistics.median(response_times), 1) if response_times else 0,
            p95_response_time_ms=round(self._percentile(response_times, 95), 1) if response_times else 0,
            p99_response_time_ms=round(self._percentile(response_times, 99), 1) if response_times else 0,
            max_response_time_ms=round(max(response_times), 1) if response_times else 0,
            error_distribution=error_dist,
            avg_blocks_per_response=round(statistics.mean([r.block_count for r in successful]), 1) if successful else 0,
            avg_sources_per_response=round(statistics.mean([r.source_count for r in successful]), 1) if successful else 0,
            thinking_usage_rate=round(sum(1 for r in self._requests if r.has_thinking) / len(self._requests), 4) if self._requests else 0,
            requests=[asdict(r) for r in self._requests],
        )

    def save_report(self, report: SoakReport, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, ensure_ascii=False, indent=2)

    @staticmethod
    def _percentile(data: list[float], p: int) -> float:
        if not data:
            return 0.0
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * p / 100
        f = int(k)
        c = f + 1
        if c >= len(sorted_data):
            return sorted_data[-1]
        return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


class SoakHealthChecker:
    """检查浸泡测试是否健康，决定是否继续"""

    def __init__(self, config):
        self._config = config
        self._consecutive_failures = 0
        self._max_consecutive_failures = 10

    def check(self, metrics: RequestMetrics) -> bool:
        if metrics.success:
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1

        if self._consecutive_failures >= self._max_consecutive_failures:
            return False  # 连续失败太多，停止

        if metrics.response_time_ms > self._config.max_response_time_seconds * 1000:
            return True  # 超时但不致命，继续

        return True

    def should_continue(self, collector: SoakCollector) -> bool:
        report = collector.generate_report()
        if report.total_requests < 10:
            return True  # 样本太少，继续
        return report.success_rate >= self._config.min_success_rate
