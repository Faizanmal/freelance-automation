from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID

from app.core.logging.logger import get_logger
from app.core.security.rate_limit import auth_rate_limiter, client_ip
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from config.settings import get_settings
from app.product_events import PRODUCT_EVENT_NAMES
from database.core.session import get_db
from database.models.audit import UserConsent
from database.models.product_event import ProductEvent
from database.models.user import User
from fastapi import APIRouter, Depends, HTTPException, Request, status

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
logger = get_logger(__name__)

class ProductEventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_key: UUID
    event_name: str = Field(min_length=3, max_length=64)
    occurred_at: datetime
    surface: Literal["discovery", "native_marketplace", "billing", "alerts", "support"] | None = None

    @field_validator("event_name")
    @classmethod
    def validate_event_name(cls, value: str) -> str:
        if value not in PRODUCT_EVENT_NAMES:
            raise ValueError("Unsupported product event")
        return value

    @field_validator("occurred_at")
    @classmethod
    def validate_event_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        now = datetime.now(timezone.utc)
        if value > now + timedelta(minutes=5) or value < now - timedelta(days=90):
            raise ValueError("Event timestamp is outside the accepted 90-day window")
        return value

class ProductEventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[ProductEventIn] = Field(min_length=1, max_length=25)


@router.post("/product-events", status_code=status.HTTP_202_ACCEPTED)
async def record_product_events(
    request: Request,
    payload: ProductEventBatch,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, int | str]:
    await auth_rate_limiter.check(
        f"product-events:{user.id}:{client_ip(request)}", limit=120, window_seconds=60
    )
    consent = await db.scalar(select(UserConsent).where(
        UserConsent.user_id == user.id, UserConsent.purpose == "analytics"
    ))
    if not consent or not consent.granted:
        raise HTTPException(status_code=403, detail="Product analytics consent is required")
    settings = get_settings()
    env = settings.environment.lower()
    environment = "production" if env == "production" else ("staging" if env == "staging" else ("test" if env in {"test", "testing"} else "development"))
    inserted = 0
    duplicate = 0
    for event in payload.events:
        existing = await db.scalar(select(ProductEvent.id).where(
            ProductEvent.user_id == user.id, ProductEvent.event_key == str(event.event_key)
        ))
        if existing:
            duplicate += 1
            continue
        db.add(ProductEvent(
            user_id=user.id,
            event_key=str(event.event_key),
            event_name=event.event_name,
            environment=environment,
            occurred_at=event.occurred_at.astimezone(timezone.utc),
            properties={"surface": event.surface} if event.surface else {},
        ))
        inserted += 1
    await db.commit()
    return {"accepted": inserted, "duplicates": duplicate, "environment": environment}


class ClientErrorIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["runtime_error", "unhandled_rejection"]


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
            scope.set_tag("error_kind", payload.kind)
            sentry_sdk.capture_message("Frontend client error", level="error")
    else:
        logger.info("Frontend client error (Sentry unset): %s", payload.kind)
    return {"detail": "accepted"}
