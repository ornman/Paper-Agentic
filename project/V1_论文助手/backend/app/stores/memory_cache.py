"""内存缓存：Redis 的替代方案（用于测试）

在测试环境或开发环境中，如果没有 Redis 服务，
可以使用这个内存存储替代。
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

import asyncio


class MemoryCache:
    """内存缓存：模拟 Redis 功能（用于测试）"""

    def __init__(self, ttl: int = 3600):
        self._ttl = ttl
        # 对话历史: session_id -> list[dict]
        self._conversations: dict[str, list[dict]] = defaultdict(list)
        # 轮询缓存: session_id -> str
        self._poll_cache: dict[str, str] = {}
        # TTL 存储: key -> expiry_time
        self._expiry: dict[str, float] = {}

    async def init(self) -> None:
        """初始化（同步操作，无需异步）"""
        # 启动清理过期数据的任务
        asyncio.create_task(self._cleanup_expired())

    async def close(self) -> None:
        """关闭（无需操作）"""
        pass

    # --- 对话历史 ---

    async def add_message(self, session_id: str, message: dict) -> None:
        key = f"conversation:{session_id}"
        self._conversations[session_id].append(message)
        # 设置过期时间
        self._expiry[key] = asyncio.get_event_loop().time() + self._ttl

    async def get_messages(self, session_id: str, limit: int = 50) -> list[dict]:
        key = f"conversation:{session_id}"
        # 检查是否过期
        if self._is_expired(key):
            return []
        messages = self._conversations.get(session_id, [])
        return messages[-limit:] if limit > 0 else messages

    async def delete_conversation(self, session_id: str) -> None:
        key = f"conversation:{session_id}"
        self._conversations.pop(session_id, None)
        self._expiry.pop(key, None)

    # --- 轮询缓存 ---

    async def set_poll_cache(self, session_id: str, content: str) -> None:
        key = f"poll:{session_id}"
        self._poll_cache[key] = content
        self._expiry[key] = asyncio.get_event_loop().time() + self._ttl

    async def get_poll_cache(self, session_id: str) -> str | None:
        key = f"poll:{session_id}"
        if self._is_expired(key):
            return None
        return self._poll_cache.get(key)

    # --- 健康检查 ---

    async def ping(self) -> bool:
        return True

    # --- 辅助方法 ---

    def _is_expired(self, key: str) -> bool:
        """检查键是否过期"""
        expiry = self._expiry.get(key)
        if expiry is None:
            return False
        return asyncio.get_event_loop().time() > expiry

    async def _cleanup_expired(self):
        """定期清理过期数据"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟清理一次
                current_time = asyncio.get_event_loop().time()
                expired_keys = [
                    key for key, expiry in self._expiry.items()
                    if expiry < current_time
                ]
                for key in expired_keys:
                    if key.startswith("conversation:"):
                        session_id = key.split(":", 1)[1]
                        self._conversations.pop(session_id, None)
                    elif key.startswith("poll:"):
                        self._poll_cache.pop(key, None)
                    self._expiry.pop(key, None)
            except asyncio.CancelledError:
                break
            except Exception:
                pass  # 忽略清理错误
