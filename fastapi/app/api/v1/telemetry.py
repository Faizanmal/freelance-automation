from __future__ import annotations

from app.core.logging.logger import get_logger
from app.core.security.rate_limit import auth_rate_limiter, client_ip
from pydantic import BaseModel, Field

from config.settings import get_settings
from fastapi import APIRouter, Request, status

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
logger = get_logger(__name__)


class ClientErrorIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    stack: str | None = Field(None, max_length=4000)
    path: str | None = Field(None, max_length=300)


@router.post("/client-error", status_code=status.HTTP_202_ACCEPTED)
async def report_client_error(
    request: Request, payload: ClientErrorIn
) -> dict[str, str]:
    await auth_rate_limiter.check(
        f"client-error:{client_ip(request)}", limit=30, window_seconds=60
    )
    settings = get_settings()
    if settings.sentry_dsn:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("source", "frontend")
            if payload.path:
                scope.set_extra("path", payload.path)
            if payload.stack:
                scope.set_extra("stack", payload.stack)
            sentry_sdk.capture_message(payload.message, level="error")
    else:
        logger.info(
            "Frontend error (Sentry unset) on %s: %s",
            payload.path or "/",
            payload.message,
        )
    return {"detail": "accepted"}
