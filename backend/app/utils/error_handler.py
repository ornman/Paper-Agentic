"""统一错误处理与重试策略"""

from __future__ import annotations

import asyncio
import random

import httpx

RETRYABLE_STATUS = {429, 502, 503, 504}
MAX_RETRIES = 3
BASE_BACKOFF = 2.0
MAX_BACKOFF = 60.0


def is_retryable(error: Exception) -> bool:
    """判断错误是否可重试"""
    if isinstance(error, (TimeoutError, asyncio.TimeoutError, httpx.RemoteProtocolError)):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in RETRYABLE_STATUS
    return False


def get_backoff(attempt: int, error: Exception | None = None) -> float:
    """计算退避时间（秒），优先读取 Retry-After 头"""
    if isinstance(error, httpx.HTTPStatusError):
        retry_after = error.response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass

    return min(MAX_BACKOFF, BASE_BACKOFF ** attempt + random.uniform(0, 2))
