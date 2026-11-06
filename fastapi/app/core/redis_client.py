from __future__ import annotations

import asyncio
import logging

import redis.asyncio as redis

from config.settings import get_settings

logger = logging.getLogger(__name__)
_client: redis.Redis | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


async def get_redis() -> redis.Redis | None:
    global _client, _client_loop
    current_loop = asyncio.get_running_loop()
    if (
        _client is not None
        and _client_loop is not None
        and (_client_loop is not current_loop or _client_loop.is_closed())
    ):
        _client = None
        _client_loop = None

    if _client is None:
        settings = get_settings()
        if not settings.redis_url:
            return None

        try:
            temp_redis = redis.from_url(settings.redis_url, decode_responses=True)
            await temp_redis.ping()
            _client = temp_redis
            _client_loop = current_loop
        except (redis.RedisError, OSError, TimeoutError, ValueError, RuntimeError) as e:
            logger.warning("Failed to connect to Redis: %s", e)
            if not settings.redis_optional:
                raise
            return None

    return _client
