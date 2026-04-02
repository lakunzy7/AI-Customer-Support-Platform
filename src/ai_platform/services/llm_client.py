import httpx
import structlog

from ai_platform.config import Settings

logger = structlog.get_logger(__name__)


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

        response = await self._client.post(
            f"{self._base_url}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()

        content: str = data["choices"][0]["message"]["content"]
        await logger.ainfo("llm_response", tokens=data.get("usage", {}))
        return content

    async def embed(self, text: str, *, model: str = "nomic-embed-text") -> list[float]:
        """Get embedding vector for a text string."""
        response = await self._client.post(
            f"{self._base_url}/embeddings",
            json={"model": model, "input": text},
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]
