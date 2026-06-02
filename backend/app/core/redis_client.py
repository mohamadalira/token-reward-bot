import json
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()
_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.close()
        _redis = None


class RedisCache:
    def __init__(self, prefix: str = "tokenbot"):
        self.prefix = prefix

    def _key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Optional[Any]:
        r = await get_redis()
        val = await r.get(self._key(key))
        if val is None:
            return None
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return val

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        r = await get_redis()
        serialized = json.dumps(value) if not isinstance(value, str) else value
        await r.setex(self._key(key), ttl, serialized)

    async def delete(self, key: str) -> None:
        r = await get_redis()
        await r.delete(self._key(key))

    async def incr(self, key: str, ttl: int = 60) -> int:
        r = await get_redis()
        full_key = self._key(key)
        count = await r.incr(full_key)
        if count == 1:
            await r.expire(full_key, ttl)
        return count
