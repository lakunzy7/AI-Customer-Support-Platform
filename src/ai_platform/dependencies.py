from functools import lru_cache

import httpx
import redis.asyncio as redis
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ai_platform.config import Settings, settings

_engine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug,
    pool_size=10,
    max_overflow=20,
)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False)

_redis: redis.Redis | None = None
_http_client: httpx.AsyncClient | None = None
_qdrant: AsyncQdrantClient | None = None


@lru_cache
def get_settings() -> Settings:
    return settings


async def get_db() -> AsyncSession:  # type: ignore[misc]
    async with _session_factory() as session:
        yield session


async def get_redis() -> redis.Redis:  # type: ignore[misc]
    global _redis  # noqa: PLW0603
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    yield _redis


async def get_http_client() -> httpx.AsyncClient:  # type: ignore[misc]
    global _http_client  # noqa: PLW0603
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=60.0)
    yield _http_client


async def get_qdrant() -> AsyncQdrantClient:  # type: ignore[misc]
    global _qdrant  # noqa: PLW0603
    if _qdrant is None:
        _qdrant = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    yield _qdrant


async def close_clients() -> None:
    """Shutdown hook — close all shared clients."""
    global _redis, _http_client, _qdrant  # noqa: PLW0603
    if _redis:
        await _redis.aclose()
        _redis = None
    if _http_client:
        await _http_client.aclose()
        _http_client = None
    if _qdrant:
        await _qdrant.close()
        _qdrant = None
    await _engine.dispose()
