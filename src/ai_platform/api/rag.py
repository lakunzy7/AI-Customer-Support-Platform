import httpx
import redis.asyncio as redis
import structlog
from fastapi import APIRouter, Depends, HTTPException
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.config import Settings
from ai_platform.dependencies import get_db, get_http_client, get_qdrant, get_redis, get_settings
from ai_platform.schemas.chat import RagRequest, RagResponse
from ai_platform.services.cache_service import CacheService
from ai_platform.services.llm_client import LLMClient
from ai_platform.services.rag_service import RagService

router = APIRouter(prefix="/v1", tags=["rag"])
logger = structlog.get_logger(__name__)


@router.post("/rag", response_model=RagResponse)
async def rag_query(
    body: RagRequest,
    redis_client: redis.Redis = Depends(get_redis),
    http_client: httpx.AsyncClient = Depends(get_http_client),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
    settings: Settings = Depends(get_settings),
) -> RagResponse:
    """Answer a question using RAG: embed → search → augmented LLM call."""
    cache = CacheService(redis_client, settings.cache_ttl_seconds)
    llm = LLMClient(http_client, settings)
    rag = RagService(llm, qdrant, cache, settings)

    try:
        result = await rag.query(body.question, top_k=body.top_k)
    except httpx.HTTPStatusError as exc:
        await logger.aerror("rag_error", status=exc.response.status_code)
        raise HTTPException(status_code=502, detail="LLM/embedding service error") from exc
    except Exception as exc:
        await logger.aerror("rag_error", error=str(exc))
        raise HTTPException(status_code=500, detail="RAG pipeline error") from exc

    return RagResponse(**result)
