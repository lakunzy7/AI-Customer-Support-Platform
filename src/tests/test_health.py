from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from ai_platform.dependencies import get_db, get_qdrant, get_redis
from ai_platform.main import app


@pytest.fixture
def client(mock_redis, mock_db_session, mock_qdrant):
    app.dependency_overrides[get_redis] = lambda: mock_redis
    app.dependency_overrides[get_db] = lambda: mock_db_session
    app.dependency_overrides[get_qdrant] = lambda: mock_qdrant
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_all_healthy(client, mock_redis, mock_db_session, mock_qdrant):
    mock_redis.ping = AsyncMock(return_value=True)

    # Mock db health check
    mock_db_session.execute = AsyncMock()

    # Mock qdrant collections
    collection_mock = AsyncMock()
    collection_mock.name = "faq_documents"
    collections_response = AsyncMock()
    collections_response.collections = [collection_mock]
    mock_qdrant.get_collections = AsyncMock(return_value=collections_response)

    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["redis"] == "ok"
    assert data["checks"]["qdrant"] == "ok"


def test_readyz_redis_down(client, mock_redis, mock_db_session, mock_qdrant):
    mock_redis.ping = AsyncMock(side_effect=ConnectionError("Redis down"))

    mock_db_session.execute = AsyncMock()

    collection_mock = AsyncMock()
    collection_mock.name = "faq_documents"
    collections_response = AsyncMock()
    collections_response.collections = [collection_mock]
    mock_qdrant.get_collections = AsyncMock(return_value=collections_response)

    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["checks"]["redis"] == "error"
