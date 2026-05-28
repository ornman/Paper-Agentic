"""Redis 运行时：会话窗口、written_context、编辑上下文

连接失败 → fallback MemoryCache，不崩主链。
运行时操作失败 → 自动降级到内存 dict。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from typing import Any

from app.data_layer.contracts.conversation import ConversationMessage
from app.service_layer.config.settings import BackendSettings

logger = logging.getLogger("paper-assistant")


# ── 内存降级缓存 ─────────────────────────────────────────────────


class _MemoryCache:
    """带 TTL 的内存缓存，作为 Redis 降级目标"""

    def __init__(self, default_ttl: int = 3600) -> None:
        self._data: dict[str, tuple[Any, float]] = {}
        self._ttl = default_ttl

    def get(self, key: str) -> Any | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ex: int | None = None) -> None:
        ttl = ex if ex is not None else self._ttl
        self._data[key] = (value, time.monotonic() + ttl)

    def delete(self, key: str) -> None:
        self._data.pop(key, None)


class _ResilientRedisClient:
    """Redis 客户端包装：操作失败自动降级到内存缓存"""

    def __init__(self, redis_client: Any, fallback: _MemoryCache) -> None:
        self._redis = redis_client
        self._fallback = fallback
        self._degraded = False

    @property
    def is_degraded(self) -> bool:
        return self._degraded

    async def get(self, key: str) -> Any | None:
        try:
            result = await self._redis.get(key)
            if self._degraded:
                logger.info("Redis recovered, exiting degraded mode")
                self._degraded = False
            return result
        except Exception as exc:
            if not self._degraded:
                logger.warning("Redis get failed, degrading to memory: %s", exc)
                self._degraded = True
            return self._fallback.get(key)

    async def set(self, key: str, value: Any, ex: int | None = None) -> None:
        try:
            await self._redis.set(key, value, ex=ex)
            if self._degraded:
                logger.info("Redis recovered, exiting degraded mode")
                self._degraded = False
        except Exception as exc:
            if not self._degraded:
                logger.warning("Redis set failed, degrading to memory: %s", exc)
                self._degraded = True
            self._fallback.set(key, value, ex=ex)

    async def ping(self) -> bool:
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False


# ── Null 降级（连接阶段失败时使用）─────────────────────────────────


class NullConversationWindowStore:
    available = False

    async def get_messages(self, session_id: str) -> list[ConversationMessage]:
        return []

    async def save_messages(self, session_id: str, messages: list[ConversationMessage]) -> None:
        return None


class NullEditorContextStore:
    available = False

    async def get(self, session_id: str) -> dict | None:
        return None

    async def put(self, snapshot: dict) -> None:
        return None


# ── Redis 实现（带运行时降级）─────────────────────────────────────


class RedisConversationWindowStore:
    available = True

    def __init__(self, resilient_client: _ResilientRedisClient, ttl_seconds: int):
        self._redis = resilient_client
        self._ttl = ttl_seconds

    async def get_messages(self, session_id: str) -> list[ConversationMessage]:
        raw = await self._redis.get(f"conversation_window:{session_id}")
        if not raw:
            return []
        try:
            payload = json.loads(raw)
            return [ConversationMessage(**item) for item in payload]
        except (json.JSONDecodeError, TypeError):
            return []

    async def save_messages(self, session_id: str, messages: list[ConversationMessage]) -> None:
        payload = json.dumps([asdict(message) for message in messages], ensure_ascii=False)
        await self._redis.set(f"conversation_window:{session_id}", payload, ex=self._ttl)


class RedisEditorContextStore:
    available = True

    def __init__(self, resilient_client: _ResilientRedisClient, ttl_seconds: int):
        self._redis = resilient_client
        self._ttl = ttl_seconds

    async def get(self, session_id: str) -> dict | None:
        raw = await self._redis.get(f"editor_context:{session_id}")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    async def put(self, snapshot: dict) -> None:
        session_id = snapshot.get("session_id", "")
        payload = json.dumps(snapshot, ensure_ascii=False)
        await self._redis.set(f"editor_context:{session_id}", payload, ex=self._ttl)


# ── 工厂函数 ─────────────────────────────────────────────────────


async def build_redis_runtime(settings: BackendSettings):
    """构建 Redis 运行时。

    连接失败 → 返回 Null stores。
    连接成功但运行时操作失败 → _ResilientRedisClient 自动降级到内存缓存。

    Returns:
        (resilient_client, window_store, editor_store, status_dict)
    """
    try:
        import redis.asyncio as redis
    except ImportError:
        return None, NullConversationWindowStore(), NullEditorContextStore(), {
            "status": "unavailable",
            "detail": "redis package missing",
        }

    try:
        raw_client = redis.from_url(settings.redis_url, decode_responses=True)
        await raw_client.ping()
    except Exception as exc:
        return None, NullConversationWindowStore(), NullEditorContextStore(), {
            "status": "unavailable",
            "detail": str(exc),
        }

    fallback = _MemoryCache(default_ttl=settings.redis_ttl_seconds)
    resilient = _ResilientRedisClient(raw_client, fallback)

    return (
        resilient,
        RedisConversationWindowStore(resilient, settings.redis_ttl_seconds),
        RedisEditorContextStore(resilient, settings.redis_ttl_seconds),
        {"status": "ok"},
    )
