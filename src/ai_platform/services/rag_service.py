import json

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import ScoredPoint

from ai_platform.config import Settings
from ai_platform.services.cache_service import CacheService
from ai_platform.services.llm_client import LLMClient

logger = structlog.get_logger(__name__)

RAG_SYSTEM_PROMPT = (
    "You are a helpful customer support assistant. "
    "Answer the user's question using ONLY the provided context. "
    "If the context doesn't contain enough information, say so. "
    "Be concise and accurate."
)


class RagService:
    """RAG pipeline: embed → vector search → augmented LLM call."""

    def __init__(
        self,
        llm: LLMClient,
        qdrant: AsyncQdrantClient,
        cache: CacheService,
        settings: Settings,
    ) -> None:
        self._llm = llm
        self._qdrant = qdrant
        self._cache = cache
        self._collection = settings.qdrant_collection

    async def query(self, question: str, top_k: int = 3) -> dict:
        # Check cache
        cached = await self._cache.get("rag", question)
        if cached:
            data = json.loads(cached)
            data["cached"] = True
            return data

        # Embed the question
        embedding = await self._llm.embed(question)

        # Search Qdrant
        search_result = await self._qdrant.query_points(
            collection_name=self._collection,
            query=embedding,
            limit=top_k,
        )
        results: list[ScoredPoint] = search_result.points

        # Build context from search results
        sources: list[str] = []
        context_parts: list[str] = []
        for point in results:
            payload = point.payload or {}
            text = payload.get("text", "")
            source = payload.get("source", "unknown")
            context_parts.append(text)
            sources.append(source)

        context = "\n\n---\n\n".join(context_parts)

        # Augmented LLM call
        messages = [
            {"role": "system", "content": RAG_SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ]
        answer = await self._llm.chat(messages)

        result = {"answer": answer, "sources": sources, "cached": False}
        await self._cache.set("rag", question, result)
        await logger.ainfo("rag_query", question_len=len(question), sources_count=len(sources))
        return result

    async def healthy(self) -> bool:
        try:
            collections = await self._qdrant.get_collections()
            return any(c.name == self._collection for c in collections.collections)
        except Exception:
            return False
