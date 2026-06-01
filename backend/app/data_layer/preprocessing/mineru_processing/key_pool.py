"""API Key 池

当前单 Key 直通。等拿到 3+ Key 后实现：
- round-robin 选 Key
- per-key semaphore (max_per_key=2)
- 429 adaptive blocking (mark_limited)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class ApiKeyPool:
    """API Key 池。当前单 Key 直通，等 3+ Key 时再实现轮转逻辑。"""

    def __init__(self, keys: list[str], max_per_key: int = 2):
        self._keys = keys

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[str]:
        """获取一个可用 Key。"""
        # TODO: 等拿到 3+ Key 后实现：
        # - round-robin 选 Key
        # - per-key semaphore (max_per_key)
        # - 429 adaptive blocking
        yield self._keys[0]

    def mark_limited(self, key: str, seconds: float) -> None:
        """429 时标记 Key 限流。单 Key 时不操作。"""
        pass
