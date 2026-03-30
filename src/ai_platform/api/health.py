import redis.asyncio as redis
from fastapi import APIRouter, Depends
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.config import Settings
from ai_platform.dependencies import get_db, get_qdrant, get_redis, get_settings
from ai_platform.schemas.health import HealthResponse, ReadyResponse
from ai_platform.services.cache_service import CacheService
from ai_platform.services.conversation_service import ConversationService
from ai_platform.services.rag_service import RagService

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """Liveness probe — the process is alive."""
    return HealthResponse(status="ok")


@router.get("/readyz", response_model=ReadyResponse)
async def readiness(
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
    settings: Settings = Depends(get_settings),
) -> ReadyResponse:
    """Readiness probe — all dependencies are reachable."""
    cache = CacheService(redis_client, settings.cache_ttl_seconds)
    conv = ConversationService(db)
    rag = RagService(None, qdrant, cache, settings)  # type: ignore[arg-type]

    checks = {
        "database": "ok" if await conv.healthy() else "error",
        "redis": "ok" if await cache.healthy() else "error",
        "qdrant": "ok" if await rag.healthy() else "error",
    }
    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return ReadyResponse(status=overall, checks=checks)
