from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config.settings import get_settings
from app.db.session import get_engine

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/ready")
async def readiness() -> dict[str, object]:
    settings = get_settings()
    checks: dict[str, object] = {"database": "ok"}

    engine = get_engine()
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))

    if settings.redis_optional:
        try:
            from app.core.redis_client import get_redis

            client = get_redis()
            await client.ping()
            checks["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["redis"] = f"skipped:{exc.__class__.__name__}"
    else:
        from app.core.redis_client import get_redis

        client = get_redis()
        await client.ping()
        checks["redis"] = "ok"

    return {"status": "ok", "checks": checks}


@router.get("/live")
async def liveness() -> dict[str, str]:
    return {"status": "alive"}
