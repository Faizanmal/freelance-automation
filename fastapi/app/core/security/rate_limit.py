from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from threading import Lock

from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[datetime]] = defaultdict(deque)
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

        client = await get_redis()
        now = datetime.now(UTC)

        if client:
            pipeline = client.pipeline()
            pipeline.zremrangebyscore(key, 0, now.timestamp() - window_seconds)
            pipeline.zcard(key)
            results = await pipeline.execute()

            count = results[1]
            if count >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=detail,
                )

            pipeline = client.pipeline()
            pipeline.zadd(key, {f"{now.timestamp()}:{id(now)}": now.timestamp()})
            pipeline.expire(key, window_seconds)
            await pipeline.execute()
        else:
            with self._lock:
                bucket = self._buckets[key]
                while bucket and now - bucket[0] > timedelta(seconds=window_seconds):
                    bucket.popleft()
                if len(bucket) >= limit:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=detail,
                    )
                bucket.append(now)


auth_rate_limiter = SlidingWindowRateLimiter()
api_rate_limiter = SlidingWindowRateLimiter()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
