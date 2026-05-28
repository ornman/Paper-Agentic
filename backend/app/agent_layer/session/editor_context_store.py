"""编辑器上下文存储：支持轮询 + 冻结副本（request_id 隔离）

live 流和冻结副本严格分离：
- put() 更新 live 状态（WPS 轮询写入）
- get() 返回最新 live 状态
- get_frozen() 返回指定 request_id 时刻的不可变快照
"""

from __future__ import annotations

import asyncio
import copy
import logging
import time
from typing import Any

logger = logging.getLogger("paper-assistant")

_POLL_INTERVAL_SECONDS = 2.0
_FROZEN_TTL_SECONDS = 300  # 冻结副本 5 分钟过期


class EditorContextStore:
    def __init__(self) -> None:
        self._store: dict[str, dict] = {}
        # request_id → (frozen_snapshot, timestamp)
        self._frozen: dict[str, tuple[dict, float]] = {}
        self._poll_task: asyncio.Task | None = None

    async def get(self, session_id: str) -> dict | None:
        return self._store.get(session_id)

    async def put(self, snapshot: dict) -> None:
        session_id = snapshot.get("session_id", "")
        self._store[session_id] = snapshot

    async def delete(self, session_id: str) -> None:
        self._store.pop(session_id, None)

    def freeze(self, session_id: str, request_id: str) -> dict | None:
        """在 request_id 时刻冻结当前编辑器上下文的不可变副本。

        返回深拷贝快照，后续 live 更新不影响已冻结的副本。
        """
        live = self._store.get(session_id)
        if live is None:
            return None
        frozen_copy = copy.deepcopy(live)
        self._frozen[request_id] = (frozen_copy, time.monotonic())
        return frozen_copy

    def get_frozen(self, request_id: str) -> dict | None:
        """获取已冻结的副本。过期则返回 None。"""
        entry = self._frozen.get(request_id)
        if entry is None:
            return None
        snapshot, frozen_at = entry
        if time.monotonic() - frozen_at > _FROZEN_TTL_SECONDS:
            self._frozen.pop(request_id, None)
            return None
        return snapshot

    def cleanup_frozen(self, max_age: float = _FROZEN_TTL_SECONDS) -> int:
        """清理过期冻结副本，返回清理数量。"""
        now = time.monotonic()
        expired = [rid for rid, (_, ts) in self._frozen.items() if now - ts > max_age]
        for rid in expired:
            self._frozen.pop(rid, None)
        return len(expired)

    # ── WPS 轮询衔接 ──────────────────────────────────────────────

    def start_polling(
        self,
        poll_fn: Any,
        session_id: str,
        interval: float = _POLL_INTERVAL_SECONDS,
    ) -> None:
        """启动 WPS 编辑器内容轮询。

        Args:
            poll_fn: 异步函数 () -> dict | None，返回最新编辑器状态
            session_id: 目标会话
            interval: 轮询间隔（秒）
        """
        if self._poll_task is not None:
            return

        async def _poll_loop() -> None:
            while True:
                try:
                    snapshot = await poll_fn()
                    if snapshot is not None:
                        snapshot["session_id"] = session_id
                        await self.put(snapshot)
                except Exception as exc:
                    logger.warning("Editor context poll failed: %s", exc)
                await asyncio.sleep(interval)

        self._poll_task = asyncio.create_task(_poll_loop())
        logger.info("Started editor context polling for session %s", session_id)

    def stop_polling(self) -> None:
        """停止轮询。"""
        if self._poll_task is not None:
            self._poll_task.cancel()
            self._poll_task = None
            logger.info("Stopped editor context polling")
