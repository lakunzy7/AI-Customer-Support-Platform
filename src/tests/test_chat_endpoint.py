from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ai_platform.dependencies import get_db, get_http_client, get_redis, get_settings
from ai_platform.main import app


@pytest.fixture
def client(mock_redis, mock_db_session, mock_http_client, settings):
    app.dependency_overrides[get_redis] = lambda: mock_redis
    app.dependency_overrides[get_db] = lambda: mock_db_session
    app.dependency_overrides[get_http_client] = lambda: mock_http_client
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_chat_new_conversation(client, mock_redis, mock_http_client, mock_db_session):
    # Cache miss
    mock_redis.get = AsyncMock(return_value=None)

    # Mock DB: get_or_create returns a new conversation
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Mock LLM response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "I can help with that!"}}],
        "usage": {},
    }
    mock_response.raise_for_status = MagicMock()
    mock_http_client.post = AsyncMock(return_value=mock_response)

    response = client.post("/v1/chat", json={"message": "Hello"})

    assert response.status_code == 200
    data = response.json()
    assert "conversation_id" in data
    assert data["message"] == "I can help with that!"
    assert data["cached"] is False


def test_chat_empty_message_rejected(client):
    response = client.post("/v1/chat", json={"message": ""})
    assert response.status_code == 422


def test_chat_message_too_long(client):
    response = client.post("/v1/chat", json={"message": "x" * 4001})
    assert response.status_code == 422
