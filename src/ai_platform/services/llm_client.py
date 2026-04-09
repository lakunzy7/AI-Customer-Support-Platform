import time
from functools import lru_cache

import httpx
import structlog

from ai_platform.config import Settings

logger = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def _get_fastembed_model(model_name: str = "nomic-ai/nomic-embed-text-v1"):
    """Load and cache the fastembed model (downloaded once on first use)."""
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=model_name)

# LLM request duration histogram (available after setup_telemetry is called)
_llm_duration = None


def _get_llm_histogram():
    global _llm_duration
    if _llm_duration is None:
        try:
            from opentelemetry import metrics

            meter = metrics.get_meter("ai_platform.llm")
            _llm_duration = meter.create_histogram(
                name="llm.request.duration",
                description="Duration of LLM API requests",
                unit="s",
            )
        except Exception:
            pass
    return _llm_duration


class LLMClient:
    """Async client for OpenAI-compatible LLM APIs (Groq, OpenRouter, etc.)."""

    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = http_client
        self._base_url = settings.llm_base_url.rstrip("/")
        self._api_key = settings.llm_api_key
        self._model = settings.llm_model

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Send a chat completion request and return the assistant message."""
        payload = {
            "model": model or self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        await logger.ainfo("llm_request", model=payload["model"], message_count=len(messages))

        start = time.perf_counter()
        response = await self._client.post(
            f"{self._base_url}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        duration = time.perf_counter() - start

        histogram = _get_llm_histogram()
        if histogram:
            histogram.record(duration, {"llm.model": payload["model"]})

        data = response.json()

        content: str = data["choices"][0]["message"]["content"]
        await logger.ainfo("llm_response", tokens=data.get("usage", {}), duration_s=round(duration, 3))
        return content

    async def embed(self, text: str, *, model: str = "nomic-ai/nomic-embed-text-v1") -> list[float]:
        """Get embedding vector using local fastembed (no external API needed)."""
        import asyncio

        embed_model = _get_fastembed_model(model)
        # fastembed is synchronous — run in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(None, lambda: list(embed_model.embed([text])))
        return embeddings[0].tolist()
