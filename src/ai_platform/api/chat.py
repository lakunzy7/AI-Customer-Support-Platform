import json

import httpx
import redis.asyncio as redis
import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.config import Settings
from ai_platform.dependencies import get_db, get_http_client, get_redis, get_settings
from ai_platform.schemas.chat import ChatRequest, ChatResponse
from ai_platform.services.cache_service import CacheService
from ai_platform.services.conversation_service import ConversationService
from ai_platform.services.llm_client import LLMClient

router = APIRouter(prefix="/v1", tags=["chat"])
logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = (
    "You are a helpful customer support assistant. "
    "Be concise, friendly, and accurate."
)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    http_client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    """Send a message and get an AI response, with caching and persistence."""
    cache = CacheService(redis_client, settings.cache_ttl_seconds)
    conv_service = ConversationService(db)
    llm = LLMClient(http_client, settings)

    # Check cache (only for new conversations / single messages)
    if body.conversation_id is None:
        cached = await cache.get("chat", body.message)
        if cached:
            conv = await conv_service.get_or_create(None)
            await conv_service.add_message(conv, "user", body.message)
            await conv_service.add_message(conv, "assistant", cached)
            await db.commit()
            return ChatResponse(conversation_id=conv.id, message=cached, cached=True)

    # Load or create conversation
    conv = await conv_service.get_or_create(body.conversation_id)
    await conv_service.add_message(conv, "user", body.message)

    # Build messages for LLM
    history = await conv_service.get_history(conv.id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]

    try:
        reply = await llm.chat(messages)
    except httpx.HTTPStatusError as exc:
        await logger.aerror("llm_error", status=exc.response.status_code)
        raise HTTPException(status_code=502, detail="LLM service error") from exc

    await conv_service.add_message(conv, "assistant", reply)
    await db.commit()

    # Cache single-turn response
    if body.conversation_id is None:
        await cache.set("chat", body.message, reply)

    return ChatResponse(conversation_id=conv.id, message=reply)
