from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.security.rate_limit import (
    SlidingWindowRateLimiter,
    client_ip,
)
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_rate_limiter_allows_under_limit():
    limiter = SlidingWindowRateLimiter(max_memory_keys=100)
    # Mock redis to None so we test in-memory fallback
    with patch("app.core.redis_client.get_redis", new=AsyncMock(return_value=None)):
        for _ in range(5):
            await limiter.check("test-user-1", limit=5, window_seconds=10)


@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_limit():
    limiter = SlidingWindowRateLimiter(max_memory_keys=100)
    with patch("app.core.redis_client.get_redis", new=AsyncMock(return_value=None)):
        for _ in range(3):
            await limiter.check("test-user-2", limit=3, window_seconds=10)

        with pytest.raises(HTTPException) as exc_info:
            await limiter.check("test-user-2", limit=3, window_seconds=10)

        assert exc_info.value.status_code == 429
        assert "Too many attempts" in exc_info.value.detail


@pytest.mark.asyncio
async def test_rate_limiter_redis_eval_atomic():
    mock_redis = AsyncMock()
    # First call: allowed (returns 1)
    mock_redis.eval = AsyncMock(return_value=1)

    limiter = SlidingWindowRateLimiter(key_prefix="rl:test")
    with patch("app.core.redis_client.get_redis", new=AsyncMock(return_value=mock_redis)):
        await limiter.check("user-redis", limit=5, window_seconds=60)
        assert mock_redis.eval.call_count == 1

        # Second call: blocked (returns 0)
        mock_redis.eval = AsyncMock(return_value=0)
        with pytest.raises(HTTPException) as exc_info:
            await limiter.check("user-redis", limit=5, window_seconds=60)
        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_rate_limiter_redis_error_falls_back_to_memory():
    import redis.asyncio as aioredis

    mock_redis = AsyncMock()
    mock_redis.eval = AsyncMock(side_effect=aioredis.ConnectionError("Redis down"))

    limiter = SlidingWindowRateLimiter(max_memory_keys=100)
    with patch("app.core.redis_client.get_redis", new=AsyncMock(return_value=mock_redis)):
        # Should gracefully fall back to memory without raising 500
        await limiter.check("user-fallback", limit=2, window_seconds=10)
        await limiter.check("user-fallback", limit=2, window_seconds=10)

        # Third attempt should be blocked by in-memory limiter
        with pytest.raises(HTTPException) as exc_info:
            await limiter.check("user-fallback", limit=2, window_seconds=10)
        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_rate_limiter_bounded_memory_lru():
    limiter = SlidingWindowRateLimiter(max_memory_keys=2)
    with patch("app.core.redis_client.get_redis", new=AsyncMock(return_value=None)):
        await limiter.check("key1", limit=5, window_seconds=10)
        await limiter.check("key2", limit=5, window_seconds=10)
        assert len(limiter._buckets) == 2

        # Adding a 3rd key should evict key1
        await limiter.check("key3", limit=5, window_seconds=10)
        assert len(limiter._buckets) == 2
        assert "key1" not in limiter._buckets
        assert "key2" in limiter._buckets
        assert "key3" in limiter._buckets


def test_client_ip_extraction():
    # Direct client IP
    req1 = MagicMock()
    req1.headers = {}
    req1.client.host = "192.168.1.50"
    assert client_ip(req1) == "192.168.1.50"

    # Forwarded IP with port and proxies
    req2 = MagicMock()
    req2.headers = {"x-forwarded-for": "203.0.113.195:443, 70.41.3.18, 150.172.238.178"}
    assert client_ip(req2) == "203.0.113.195"

    # Unknown
    req3 = MagicMock()
    req3.headers = {}
    req3.client = None
    assert client_ip(req3) == "unknown"

