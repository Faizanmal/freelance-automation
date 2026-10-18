from __future__ import annotations

import logging

import redis.asyncio as redis

from config.settings import get_settings

logger = logging.getLogger(__name__)
_client: redis.Redis | None = None


async def get_redis() -> redis.Redis | None:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.redis_url:
            return None

        try:
            temp_redis = redis.from_url(settings.redis_url, decode_responses=True)
            await temp_redis.ping()
            _client = temp_redis
        except (redis.RedisError, OSError, TimeoutError, ValueError) as e:
            logger.warning("Failed to connect to Redis: %s", e)
            if not settings.redis_optional:
                raise
            return None

    return _client
