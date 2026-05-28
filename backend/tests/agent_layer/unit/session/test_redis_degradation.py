"""Redis 降级策略单元测试"""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent_layer.session.redis_runtime import (
    NullConversationWindowStore,
    NullEditorContextStore,
    RedisConversationWindowStore,
    RedisEditorContextStore,
    _MemoryCache,
    _ResilientRedisClient,
)


# ── _MemoryCache ──────────────────────────────────────────────────


class TestMemoryCache:
    def test_set_and_get(self):
        cache = _MemoryCache()
        cache.set("k1", "v1")
        assert cache.get("k1") == "v1"

    def test_get_missing(self):
        cache = _MemoryCache()
        assert cache.get("nope") is None

    def test_ttl_expiry(self):
        cache = _MemoryCache()
        cache.set("k1", "v1", ex=0)
        time.sleep(0.01)
        assert cache.get("k1") is None

    def test_delete(self):
        cache = _MemoryCache()
        cache.set("k1", "v1")
        cache.delete("k1")
        assert cache.get("k1") is None

    def test_delete_nonexistent(self):
        cache = _MemoryCache()
        cache.delete("nope")  # should not raise


# ── _ResilientRedisClient ─────────────────────────────────────────


class TestResilientRedisClient:
    @pytest.fixture
    def mock_redis(self):
        client = AsyncMock()
        client.get = AsyncMock(return_value='{"data": "from_redis"}')
        client.set = AsyncMock()
        client.ping = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def resilient(self, mock_redis):
        return _ResilientRedisClient(mock_redis, _MemoryCache())

    async def test_normal_get(self, resilient, mock_redis):
        result = await resilient.get("key")
        assert result == '{"data": "from_redis"}'
        mock_redis.get.assert_awaited_once_with("key")

    async def test_normal_set(self, resilient, mock_redis):
        await resilient.set("key", "value", ex=60)
        mock_redis.set.assert_awaited_once_with("key", "value", ex=60)

    async def test_get_fallback_on_error(self, mock_redis):
        mock_redis.get = AsyncMock(side_effect=ConnectionError("redis down"))
        cache = _MemoryCache()
        cache.set("key", "cached_value")
        resilient = _ResilientRedisClient(mock_redis, cache)

        result = await resilient.get("key")
        assert result == "cached_value"
        assert resilient.is_degraded

    async def test_set_fallback_on_error(self, mock_redis):
        mock_redis.set = AsyncMock(side_effect=ConnectionError("redis down"))
        cache = _MemoryCache()
        resilient = _ResilientRedisClient(mock_redis, cache)

        await resilient.set("key", "value", ex=60)
        assert cache.get("key") == "value"
        assert resilient.is_degraded

    async def test_recovery_from_degraded(self, mock_redis):
        # 先降级
        mock_redis.get = AsyncMock(side_effect=ConnectionError("down"))
        cache = _MemoryCache()
        cache.set("key", "fallback")
        resilient = _ResilientRedisClient(mock_redis, cache)

        await resilient.get("key")
        assert resilient.is_degraded

        # 恢复
        mock_redis.get = AsyncMock(return_value="recovered")
        result = await resilient.get("key")
        assert result == "recovered"
        assert not resilient.is_degraded

    async def test_ping_success(self, resilient, mock_redis):
        assert await resilient.ping() is True

    async def test_ping_failure(self, mock_redis):
        mock_redis.ping = AsyncMock(side_effect=ConnectionError("down"))
        resilient = _ResilientRedisClient(mock_redis, _MemoryCache())
        assert await resilient.ping() is False


# ── Redis stores with degraded client ─────────────────────────────


class TestRedisStoresDegraded:
    async def test_window_store_fallback(self):
        """Redis 挂掉后 window_store 自动降级到内存"""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(side_effect=ConnectionError("down"))
        mock_redis.get = AsyncMock(side_effect=ConnectionError("down"))

        resilient = _ResilientRedisClient(mock_redis, _MemoryCache(default_ttl=60))
        store = RedisConversationWindowStore(resilient, ttl_seconds=60)

        # save 不抛异常
        await store.save_messages("s1", [])
        assert resilient.is_degraded

    async def test_editor_store_fallback(self):
        """Redis 挂掉后 editor_store 自动降级到内存"""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(side_effect=ConnectionError("down"))
        mock_redis.get = AsyncMock(side_effect=ConnectionError("down"))

        resilient = _ResilientRedisClient(mock_redis, _MemoryCache(default_ttl=60))
        store = RedisEditorContextStore(resilient, ttl_seconds=60)

        await store.put({"session_id": "s1", "draft": "test"})
        assert resilient.is_degraded


# ── Null stores ───────────────────────────────────────────────────


class TestNullStores:
    async def test_null_window(self):
        store = NullConversationWindowStore()
        assert store.available is False
        assert await store.get_messages("s1") == []
        await store.save_messages("s1", [])  # should not raise

    async def test_null_editor(self):
        store = NullEditorContextStore()
        assert store.available is False
        assert await store.get("s1") is None
        await store.put({"session_id": "s1"})  # should not raise
