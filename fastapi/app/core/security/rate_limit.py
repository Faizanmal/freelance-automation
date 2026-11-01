from __future__ import annotations

from collections import OrderedDict, deque
from datetime import UTC, datetime, timedelta
from threading import Lock
import uuid

import redis.asyncio as aioredis
from app.core.logging.logger import get_logger
from fastapi import HTTPException, Request, status

logger = get_logger(__name__)

# Atomic sliding-window rate limit Lua script
# Eliminates TOCTOU race condition in high-concurrency / multi-worker deployments
_REDIS_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local window_start = tonumber(ARGV[1])
local now_score = tonumber(ARGV[2])
local member = ARGV[3]
local limit = tonumber(ARGV[4])
local window_seconds = tonumber(ARGV[5])

redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)
local current_count = redis.call('ZCARD', key)

if current_count < limit then
    redis.call('ZADD', key, now_score, member)
    redis.call('EXPIRE', key, window_seconds)
    return 1
else
    return 0
end
"""


class SlidingWindowRateLimiter:
    """Production sliding-window rate limiter.

    Supports distributed Redis with an atomic Lua script to eliminate TOCTOU race conditions.
    Falls back gracefully to a bounded in-memory LRU store when Redis is unavailable or disconnected.
    """

    def __init__(self, max_memory_keys: int = 10_000, key_prefix: str = "rl") -> None:
        self._max_memory_keys = max_memory_keys
        self._key_prefix = key_prefix
        self._buckets: OrderedDict[str, deque[datetime]] = OrderedDict()
        self._lock = Lock()

    async def check(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        detail: str = "Too many attempts. Try again shortly.",
    ) -> None:
        from app.core.redis_client import get_redis

        now = datetime.now(UTC)
        client = None

        try:
            client = await get_redis()
        except Exception as exc:
            logger.warning("Failed to obtain Redis client for rate limiter: %s", exc)

        if client is not None:
            redis_key = f"{self._key_prefix}:{key}"
            window_start = now.timestamp() - window_seconds
            now_ts = now.timestamp()
            member = f"{now_ts}:{uuid.uuid4().hex[:8]}"

            try:
                allowed = await client.eval(
                    _REDIS_SLIDING_WINDOW_LUA,
                    1,
                    redis_key,
                    window_start,
                    now_ts,
                    member,
                    limit,
                    max(window_seconds, 1),
                )
                if not allowed:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=detail,
                    )
                return
            except HTTPException:
                raise
            except (aioredis.RedisError, OSError, TimeoutError) as exc:
                logger.warning(
                    "Redis rate limit check failed for key %s; falling back to in-memory store: %s",
                    key,
                    exc,
                )

        # Fallback to in-memory sliding window
        self._check_memory(key, now, limit=limit, window_seconds=window_seconds, detail=detail)

    def _check_memory(
        self,
        key: str,
        now: datetime,
        *,
        limit: int,
        window_seconds: int,
        detail: str,
    ) -> None:
        with self._lock:
            # Memory safety: prune LRU entries if capacity reached
            if len(self._buckets) >= self._max_memory_keys and key not in self._buckets:
                self._buckets.popitem(last=False)

            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = deque()
                self._buckets[key] = bucket

            # Refresh LRU order
            self._buckets.move_to_end(key)

            cutoff = now - timedelta(seconds=window_seconds)
            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=detail,
                )

            bucket.append(now)

    def reset(self) -> None:
        """Clear in-memory state (useful for tests)."""
        with self._lock:
            self._buckets.clear()


auth_rate_limiter = SlidingWindowRateLimiter(key_prefix="rl:auth")
api_rate_limiter = SlidingWindowRateLimiter(key_prefix="rl:api")


def client_ip(request: Request) -> str:
    """Extract and sanitize client IP address."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        raw_ip = forwarded.split(",")[0].strip()
        if raw_ip:
            # Strip port if present (e.g. 192.168.1.1:8080)
            if ":" in raw_ip and not raw_ip.startswith("[") and raw_ip.count(":") == 1:
                raw_ip = raw_ip.split(":")[0]
            return raw_ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
