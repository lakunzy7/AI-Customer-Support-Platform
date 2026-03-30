import hashlib
import json

import redis.asyncio as redis
import structlog

logger = structlog.get_logger(__name__)


class CacheService:
    """Redis cache with SHA-256 keys and configurable TTL."""

    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 3600) -> None:
        self._redis = redis_client
        self._ttl = ttl_seconds

    @staticmethod
    def _make_key(prefix: str, data: str) -> str:
        digest = hashlib.sha256(data.encode()).hexdigest()[:16]
        return f"{prefix}:{digest}"

    async def get(self, prefix: str, data: str) -> str | None:
        key = self._make_key(prefix, data)
        value = await self._redis.get(key)
        if value is not None:
            await logger.ainfo("cache_hit", key=key)
        return value

    async def set(self, prefix: str, data: str, value: str | dict) -> None:
        key = self._make_key(prefix, data)
        serialized = json.dumps(value) if isinstance(value, dict) else value
        await self._redis.setex(key, self._ttl, serialized)
        await logger.ainfo("cache_set", key=key, ttl=self._ttl)

    async def healthy(self) -> bool:
        try:
            return await self._redis.ping()
        except Exception:
            return False
