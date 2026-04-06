from unittest.mock import AsyncMock

import pytest

from ai_platform.services.cache_service import CacheService


@pytest.fixture
def cache(mock_redis):
    return CacheService(mock_redis, ttl_seconds=300)


@pytest.mark.asyncio
async def test_cache_miss(cache, mock_redis):
    mock_redis.get = AsyncMock(return_value=None)
    result = await cache.get("test", "some data")
    assert result is None


@pytest.mark.asyncio
async def test_cache_hit(cache, mock_redis):
    mock_redis.get = AsyncMock(return_value="cached value")
    result = await cache.get("test", "some data")
    assert result == "cached value"


@pytest.mark.asyncio
async def test_cache_set_string(cache, mock_redis):
    await cache.set("test", "some data", "value")
    mock_redis.setex.assert_called_once()
    args = mock_redis.setex.call_args[0]
    assert args[0].startswith("test:")
    assert args[1] == 300
    assert args[2] == "value"


@pytest.mark.asyncio
async def test_cache_set_dict(cache, mock_redis):
    await cache.set("test", "data", {"key": "val"})
    mock_redis.setex.assert_called_once()
    args = mock_redis.setex.call_args[0]
    assert '"key"' in args[2]


@pytest.mark.asyncio
async def test_cache_key_deterministic(cache, mock_redis):
    mock_redis.get = AsyncMock(return_value=None)
    await cache.get("prefix", "same input")
    key1 = mock_redis.get.call_args[0][0]

    await cache.get("prefix", "same input")
    key2 = mock_redis.get.call_args[0][0]

    assert key1 == key2


@pytest.mark.asyncio
async def test_healthy_returns_true(cache, mock_redis):
    mock_redis.ping = AsyncMock(return_value=True)
    assert await cache.healthy() is True


@pytest.mark.asyncio
async def test_healthy_returns_false_on_error(cache, mock_redis):
    mock_redis.ping = AsyncMock(side_effect=ConnectionError)
    assert await cache.healthy() is False
