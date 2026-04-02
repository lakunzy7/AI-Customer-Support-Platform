import asyncio
import json
from pathlib import Path

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

TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml",
    ".py", ".js", ".ts", ".html", ".css", ".sql", ".sh", ".log",
}

router = APIRouter(prefix="/v1", tags=["chat"])
logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = (
    "You are a helpful customer support assistant. "
    "Be concise, friendly, and accurate."
)

TITLE_PROMPT = "Summarize this conversation in 3-5 words as a short title. Reply with ONLY the title, nothing else."


async def _generate_title(
    llm: LLMClient,
    conv_service: ConversationService,
    db: AsyncSession,
    conversation_id: str,
    user_message: str,
) -> None:
    """Background task: generate a short title for a new conversation."""
    try:
        messages = [
            {"role": "user", "content": user_message},
            {"role": "user", "content": TITLE_PROMPT},
        ]
        title = await llm.chat(messages)
        title = title.strip().strip('"').strip("'")[:200]
        await conv_service.set_title(conversation_id, title)
        await db.commit()
    except Exception:
        await logger.awarning("title_generation_failed", conversation_id=conversation_id)


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

    is_new_conversation = body.conversation_id is None

    # Check cache (only for new conversations / single messages)
    if is_new_conversation:
        cached = await cache.get("chat", body.message)
        if cached:
            conv = await conv_service.get_or_create(None)
            await conv_service.add_message(conv, "user", body.message)
            await conv_service.add_message(conv, "assistant", cached)
            await db.commit()
            asyncio.create_task(
                _generate_title(llm, ConversationService(db), db, conv.id, body.message)
            )
            return ChatResponse(conversation_id=conv.id, message=cached, cached=True)

    # Load or create conversation
    conv = await conv_service.get_or_create(body.conversation_id)
    await conv_service.add_message(conv, "user", body.message)

    # Build messages for LLM
    history = await conv_service.get_history(conv.id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]

    # Attach file contents as context
    if body.file_ids:
        upload_dir = Path(settings.upload_dir)
        file_context_parts = []
        for fid in body.file_ids[:5]:  # max 5 files
            matches = list(upload_dir.glob(f"{fid}.*"))
            if not matches:
                continue
            fpath = matches[0]
            ext = fpath.suffix.lower()
            if ext in TEXT_EXTENSIONS:
                try:
                    text = fpath.read_text(errors="replace")[:8000]
                    file_context_parts.append(f"[File: {fpath.name}]\n{text}")
                except Exception:
                    pass
            else:
                file_context_parts.append(f"[File: {fpath.name} ({ext} binary file attached)]")
        if file_context_parts:
            file_context = "\n\n".join(file_context_parts)
            messages.insert(1, {"role": "user", "content": f"Attached files:\n\n{file_context}"})

    try:
        reply = await llm.chat(messages)
    except httpx.HTTPStatusError as exc:
        await logger.aerror("llm_error", status=exc.response.status_code)
        raise HTTPException(status_code=502, detail="LLM service error") from exc

    await conv_service.add_message(conv, "assistant", reply)
    await db.commit()

    # Cache single-turn response
    if is_new_conversation:
        await cache.set("chat", body.message, reply)

    # Auto-generate title for new conversations
    if is_new_conversation:
        asyncio.create_task(
            _generate_title(llm, ConversationService(db), db, conv.id, body.message)
        )

    return ChatResponse(conversation_id=conv.id, message=reply)
