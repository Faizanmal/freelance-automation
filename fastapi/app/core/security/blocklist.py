from __future__ import annotations

import logging
from datetime import UTC, datetime

import redis.asyncio as redis

from config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class JWTBlocklist:
    def __init__(self) -> None:
        self._redis: redis.Redis | None = None
        self._memory_blocklist: set[str] = set()

    async def get_redis(self):
        from app.core.redis_client import get_redis

        return await get_redis()

    async def block_token(self, jti: str, exp: datetime) -> None:
        client = await self.get_redis()
        if client:
            now = datetime.now(UTC)
            ttl = int((exp - now).total_seconds())
            if ttl > 0:
                await client.setex(f"blocklist:{jti}", ttl, "1")
        else:
            # Fallback to in-memory blocklist if Redis is not available
            self._memory_blocklist.add(jti)

    async def is_blocked(self, jti: str) -> bool:
        client = await self.get_redis()
        if client:
            result = await client.exists(f"blocklist:{jti}")
            return result > 0
        return jti in self._memory_blocklist


blocklist = JWTBlocklist()
