"""令牌桶速率限制器"""

from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """令牌桶速率限制器，支持 async with 上下文。

    用法::

        limiter = RateLimiter(rate=5.0)  # 5 请求/秒

        async with limiter:
            await client.post(...)
    """

    def __init__(self, rate: float, burst: int | None = None):
        self._rate = rate
        self._burst = burst or max(1, int(rate))
        self._tokens = float(self._burst)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self._rate
            await asyncio.sleep(wait)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._last = now

    async def __aenter__(self) -> RateLimiter:
        await self.acquire()
        return self

    async def __aexit__(self, *args: object) -> None:
        pass
