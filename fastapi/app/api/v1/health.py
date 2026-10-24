from __future__ import annotations

from redis.exceptions import RedisError
from sqlalchemy import text

from config.settings import get_settings
from database.core.session import get_engine
from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
@router.get("/")
async def health() -> dict[str, str]:
    """Simple liveness alias at /health (and /api/v1/health)."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness() -> dict[str, object]:
    settings = get_settings()
    checks: dict[str, object] = {"database": "ok"}

    engine = get_engine()
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))

    from app.core.redis_client import get_redis

    try:
        client = await get_redis()
    except (RedisError, OSError, TimeoutError, ValueError) as exc:
        checks["redis"] = f"down:{exc.__class__.__name__}"
        return {"status": "degraded", "checks": checks}

    if client is None:
        checks["redis"] = "skipped" if settings.redis_optional else "down"
    else:
        checks["redis"] = "ok"

    if checks["redis"] == "down":
        return {"status": "degraded", "checks": checks}

    return {"status": "ok", "checks": checks}


@router.get("/live")
async def liveness() -> dict[str, str]:
    return {"status": "alive"}
