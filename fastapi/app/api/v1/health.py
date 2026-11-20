from __future__ import annotations

import asyncio

from redis.exceptions import RedisError
from sqlalchemy import text
from starlette.responses import JSONResponse

from config.settings import get_settings
from database.core.session import get_engine
from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])

_CHECK_TIMEOUT_S = 2.0


@router.get("")
@router.get("/")
async def health() -> dict[str, str]:
    """Simple liveness alias at /health (and /api/v1/health)."""
    return {"status": "ok"}


async def _check_database() -> str:
    engine = get_engine()
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return "ok"


async def _check_redis(settings) -> str:
    from app.core.redis_client import get_redis

    try:
        client = await get_redis()
    except (RedisError, OSError, TimeoutError, ValueError) as exc:
        return f"down:{exc.__class__.__name__}"

    if client is None:
        return "skipped" if settings.redis_optional else "down"
    return "ok"


@router.get("/ready")
async def readiness():
    """
    Dependency readiness.

    - 200 + status=ok when critical deps are healthy
    - 200 + status=degraded when optional deps (workers/beat) are idle/stale
    - 503 when database (or required Redis) is down
    Public payload never includes connection strings or secrets.
    """
    settings = get_settings()
    checks: dict[str, object] = {}

    try:
        checks["database"] = await asyncio.wait_for(
            _check_database(), timeout=_CHECK_TIMEOUT_S
        )
    except Exception as exc:  # noqa: BLE001 — map any DB failure to down
        checks["database"] = f"down:{exc.__class__.__name__}"

    try:
        checks["redis"] = await asyncio.wait_for(
            _check_redis(settings), timeout=_CHECK_TIMEOUT_S
        )
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"down:{exc.__class__.__name__}"

    # Worker ping (Celery inspect) — short timeout; never raise.
    try:
        from workers.availability import celery_workers_online

        workers_online = await asyncio.to_thread(
            celery_workers_online, _CHECK_TIMEOUT_S
        )
        checks["workers"] = "ok" if workers_online else "idle"
    except Exception:
        checks["workers"] = "skipped"

    try:
        from workers.heartbeat import read_heartbeats

        beats = await asyncio.to_thread(read_heartbeats)
        checks["worker_heartbeat"] = beats.get("worker", "unknown")
        checks["beat_heartbeat"] = beats.get("beat", "unknown")
    except Exception:
        checks["worker_heartbeat"] = "unknown"
        checks["beat_heartbeat"] = "unknown"

    db_ok = checks.get("database") == "ok"
    redis_ok = checks.get("redis") in {"ok", "skipped"}
    critical_ok = db_ok and redis_ok

    workers_ok = checks.get("workers") in {"ok", "skipped"}
    # unknown = Redis optional / never touched (local API-only); stale = was seen, expired
    heartbeat_ok = checks.get("worker_heartbeat") != "stale" and checks.get(
        "beat_heartbeat"
    ) != "stale"

    if not critical_ok:
        return JSONResponse(
            {"status": "unavailable", "checks": checks},
            status_code=503,
        )

    if not workers_ok or not heartbeat_ok:
        return {"status": "degraded", "checks": checks}

    return {"status": "ok", "checks": checks}


@router.get("/live")
async def liveness() -> dict[str, str]:
    return {"status": "alive"}
