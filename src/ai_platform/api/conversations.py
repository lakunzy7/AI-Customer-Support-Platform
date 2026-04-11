import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.dependencies import get_db
from ai_platform.services.conversation_service import ConversationService

router = APIRouter(prefix="/v1", tags=["conversations"])
logger = structlog.get_logger(__name__)


class ConversationSummary(BaseModel):
    id: str
    title: str | None = None
    created_at: str


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: str


class MessagesResponse(BaseModel):
    conversation_id: str
    messages: list[MessageOut]


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    db: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    """List all conversations, newest first."""
    svc = ConversationService(db)
    convs = await svc.list_conversations()
    return ConversationListResponse(
        conversations=[
            ConversationSummary(
                id=c.id,
                title=c.title,
                created_at=c.created_at.isoformat(),
            )
            for c in convs
        ]
    )


@router.get("/conversations/{conversation_id}/messages", response_model=MessagesResponse)
async def get_conversation_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
) -> MessagesResponse:
    """Get all messages in a conversation."""
    svc = ConversationService(db)
    conv = await svc.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    # get_history returns dicts, we need created_at too
    from sqlalchemy import select

    from ai_platform.models.conversation import Message

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    msgs = result.scalars().all()
    return MessagesResponse(
        conversation_id=conversation_id,
        messages=[
            MessageOut(role=m.role, content=m.content, created_at=m.created_at.isoformat())
            for m in msgs
        ],
    )


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    body: RenameRequest,
    db: AsyncSession = Depends(get_db),
):
    """Rename a conversation."""
    svc = ConversationService(db)
    conv = await svc.rename_conversation(conversation_id, body.title)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.commit()
    return {"id": conv.id, "title": conv.title}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    svc = ConversationService(db)
    deleted = await svc.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.commit()
    return {"deleted": True}
