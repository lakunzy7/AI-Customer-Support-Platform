from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
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
    assert payload["model"] == "llama-3.3-70b-versatile"


@pytest.mark.asyncio
async def test_embed_returns_vector(llm_client, mock_http_client):
    mock_model = MagicMock()
    mock_model.embed.return_value = [np.array([0.1, 0.2, 0.3])]

    with patch("ai_platform.services.llm_client._get_fastembed_model", return_value=mock_model):
        result = await llm_client.embed("test text")

    assert result == [pytest.approx(0.1), pytest.approx(0.2), pytest.approx(0.3)]
    mock_model.embed.assert_called_once_with(["test text"])
