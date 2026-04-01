import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ulid import ULID

from ai_platform.models.conversation import Conversation, Message

logger = structlog.get_logger(__name__)


class ConversationService:
    """Manage conversation history in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, conversation_id: str | None) -> Conversation:
        if conversation_id:
            result = await self._session.execute(
                select(Conversation)
                .options(selectinload(Conversation.messages))
                .where(Conversation.id == conversation_id)
            )
            conv = result.scalar_one_or_none()
            if conv:
                return conv

        conv = Conversation(id=str(ULID()))
        self._session.add(conv)
        await self._session.flush()
        await logger.ainfo("conversation_created", conversation_id=conv.id)
        return conv

    async def add_message(self, conversation: Conversation, role: str, content: str) -> Message:
        msg = Message(id=str(ULID()), conversation_id=conversation.id, role=role, content=content)
        self._session.add(msg)
        await self._session.flush()
        return msg

    async def get_history(self, conversation_id: str) -> list[dict[str, str]]:
        """Fetch message history for a conversation from DB."""
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()
        return [{"role": m.role, "content": m.content} for m in messages]

    async def healthy(self) -> bool:
        try:
            await self._session.execute(select(1))
            return True
        except Exception:
            return False
