from __future__ import annotations

import json

import redis.asyncio as aioredis


class RedisCache:
    def __init__(self, url: str = "redis://localhost:6379/0", ttl: int = 3600):
        self._url = url
        self._ttl = ttl
        self._redis: aioredis.Redis | None = None

    async def init(self) -> None:
        self._redis = aioredis.from_url(self._url, decode_responses=True)
        await self._redis.ping()

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()

    # --- 对话历史 ---

    async def add_message(self, session_id: str, message: dict) -> None:
        key = f"conversation:{session_id}"
        await self._redis.rpush(key, json.dumps(message, ensure_ascii=False))
        await self._redis.expire(key, self._ttl)

    async def get_messages(self, session_id: str, limit: int = 50) -> list[dict]:
        key = f"conversation:{session_id}"
        raw = await self._redis.lrange(key, -limit, -1)
        return [json.loads(m) for m in raw]

    async def delete_conversation(self, session_id: str) -> None:
        await self._redis.delete(f"conversation:{session_id}")

    # --- 轮询缓存 ---

    async def set_poll_cache(self, session_id: str, content: str) -> None:
        key = f"poll:{session_id}"
        await self._redis.set(key, content, ex=self._ttl)

    async def get_poll_cache(self, session_id: str) -> str | None:
        return await self._redis.get(f"poll:{session_id}")

    # --- 健康检查 ---

    async def ping(self) -> bool:
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False
