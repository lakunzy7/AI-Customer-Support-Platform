from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from ai_platform.config import Settings


@pytest.fixture
def settings():
    return Settings(
        app_env="test",
        llm_api_key="test-key",
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
    )


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.setex = AsyncMock()
    r.ping = AsyncMock(return_value=True)
    return r


@pytest.fixture
def mock_http_client():
    client = AsyncMock()
    client.post = AsyncMock()
    return client


@pytest.fixture
def mock_qdrant():
    client = AsyncMock()
    return client


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session
