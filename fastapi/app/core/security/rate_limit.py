from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock

from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = Lock()

    async def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        from app.core.redis_client import get_redis
        client = await get_redis()
        now = datetime.now(timezone.utc)
        
        if client:
            pipeline = client.pipeline()
            pipeline.zremrangebyscore(key, 0, now.timestamp() - window_seconds)
            pipeline.zcard(key)
            pipeline.zadd(key, {str(now.timestamp()): now.timestamp()})
            pipeline.expire(key, window_seconds)
            results = await pipeline.execute()
            
            # The second command in pipeline is zcard (count)
            count = results[1]
            if count >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many attempts. Try again shortly.",
                )
        else:
            with self._lock:
                bucket = self._buckets[key]
                while bucket and now - bucket[0] > timedelta(seconds=window_seconds):
                    bucket.popleft()
                if len(bucket) >= limit:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Too many attempts. Try again shortly.",
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
