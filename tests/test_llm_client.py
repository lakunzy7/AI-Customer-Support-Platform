from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_platform.services.llm_client import LLMClient


@pytest.fixture
def llm_client(mock_http_client, settings):
    return LLMClient(mock_http_client, settings)


@pytest.mark.asyncio
async def test_chat_returns_content(llm_client, mock_http_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello! How can I help?"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 8},
    }
    mock_response.raise_for_status = MagicMock()
    mock_http_client.post = AsyncMock(return_value=mock_response)

    result = await llm_client.chat([{"role": "user", "content": "Hi"}])

    assert result == "Hello! How can I help?"
    mock_http_client.post.assert_called_once()

    call_args = mock_http_client.post.call_args
    assert "/chat/completions" in call_args[0][0]
    payload = call_args[1]["json"]
    assert payload["model"] == "anthropic/claude-sonnet-4-20250514"


@pytest.mark.asyncio
async def test_embed_returns_vector(llm_client, mock_http_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [{"embedding": [0.1, 0.2, 0.3]}],
    }
    mock_response.raise_for_status = MagicMock()
    mock_http_client.post = AsyncMock(return_value=mock_response)

    result = await llm_client.embed("test text")

    assert result == [0.1, 0.2, 0.3]
