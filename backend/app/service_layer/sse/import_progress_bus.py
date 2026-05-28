"""导入进度 SSE 总线 — 内存 pub/sub"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class ImportProgressBus:
    """基于 asyncio.Queue 的导入进度 pub/sub"""

    _queues: dict[str, list[asyncio.Queue]] = field(default_factory=dict)

    def subscribe(self, task_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.setdefault(task_id, []).append(q)
        return q

    def unsubscribe(self, task_id: str, q: asyncio.Queue) -> None:
        if task_id in self._queues:
            self._queues[task_id] = [x for x in self._queues[task_id] if x is not q]
            if not self._queues[task_id]:
                del self._queues[task_id]

    async def publish(self, task_id: str, event: dict) -> None:
        for q in self._queues.get(task_id, []):
            await q.put(event)
