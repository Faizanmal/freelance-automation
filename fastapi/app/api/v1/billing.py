from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import time
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from backend.application.services.billing import (
    PLAN_FREE,
    PLAN_PRO,
    PLANS,
    is_pro,
    limits_for_user,
    normalize_plan,
)
from backend.application.services.india_compliance import IndiaEntityComplianceAudit
from backend.application.services.quota_service import QuotaService
from backend.application.services.unit_economics import UnitEconomicsService
from config.settings import get_settings
from database.core.session import get_db
from database.models.billing import (
    BillingWebhookEvent,
    SubscriptionLifecycleRecord,
)
from database.models.user import User

router = APIRouter(prefix="/billing", tags=["billing"])

GRACE_PERIOD_DAYS = 3
WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS = 300


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CheckoutResponse(BaseModel):
    url: str
    mode: str


class BillingStatus(BaseModel):
    plan: str
    subscription_status: str
    is_pro: bool
    stripe_enabled: bool
    dev_activate_allowed: bool
    limits: dict[str, object]
    features: list[str]


class ReserveQuotaRequest(BaseModel):
    feature: str = Field(..., max_length=64, description="Feature code (copilot_run, token_budget, search_call)")
    units: int = Field(default=1, ge=1, le=50000)
    idempotency_key: str | None = Field(default=None, max_length=128)
    workspace_id: str | None = Field(default=None, max_length=64)


class CommitQuotaRequest(BaseModel):
    reservation_token: str = Field(..., max_length=64)
    units_used: int | None = Field(default=None, ge=0)
    cost_estimate_usd: float = Field(default=0.0, ge=0)


class ReleaseQuotaRequest(BaseModel):
    reservation_token: str = Field(..., max_length=64)


# ---------------------------------------------------------------------------
# Public Plan Listing & User Status
# ---------------------------------------------------------------------------

@router.get("/plans")
async def list_plans() -> dict[str, object]:
    settings = get_settings()
    return {
        "stripe_enabled": settings.stripe_enabled,
        "dev_activate_allowed": (not settings.is_production) and (not settings.stripe_enabled),
        "currency": "USD",
        "cancellation_policy": "Cancel anytime. You retain full data export and access to Hunt Rules.",
        "ranking_policy": "Pro never changes or buys intrinsic job match ranking.",
        "plans": [
            {
                "id": plan.name,
                "price_label": plan.price_label,
                "marketplace": plan.marketplace,
                "scrape_limit": plan.scrape_limit,
                "max_digest": plan.max_digest,
                "daily_scrape_runs": plan.daily_scrape_runs,
                "channels": sorted(plan.allowed_channels),
                "features": list(plan.features),
            }
            for plan in PLANS.values()
        ],
    }


@router.get("/me", response_model=BillingStatus)
async def my_billing(
    user: Annotated[User, Depends(get_current_user)],
) -> BillingStatus:
    settings = get_settings()
    limits = limits_for_user(user)
    return BillingStatus(
        plan=normalize_plan(user.plan),
        subscription_status=user.subscription_status or "inactive",
        is_pro=is_pro(user),
        stripe_enabled=settings.stripe_enabled,
        dev_activate_allowed=(not settings.is_production) and (not settings.stripe_enabled),
        limits={
            "scrape_limit": limits.scrape_limit,
            "max_digest": limits.max_digest,
            "daily_scrape_runs": limits.daily_scrape_runs,
            "marketplace": limits.marketplace,
            "channels": sorted(limits.allowed_channels),
            "sources": list(limits.allowed_sources),
        },
        features=list(limits.features),
    )


# ---------------------------------------------------------------------------
# Quota Reservation & Usage Endpoints
# ---------------------------------------------------------------------------

@router.post("/quotas/reserve")
async def reserve_quota(
    payload: ReserveQuotaRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Atomically reserve units for expensive AI or search operations."""
    qs = QuotaService(session)
    result = await qs.reserve_quota(
        user=user,
        feature=payload.feature,
        units=payload.units,
        idempotency_key=payload.idempotency_key,
        workspace_id=payload.workspace_id,
    )
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=result.reason or "Quota exceeded for current billing period",
        )
    return result.to_dict()


@router.post("/quotas/commit")
async def commit_quota(
    payload: CommitQuotaRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Commit quota reservation with actual units consumed."""
    qs = QuotaService(session)
    success = await qs.commit_quota(
        reservation_token=payload.reservation_token,
        units_used=payload.units_used,
        cost_estimate_usd=payload.cost_estimate_usd,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Active reservation token not found")
    return {"status": "committed", "reservation_token": payload.reservation_token}


@router.post("/quotas/release")
async def release_quota(
    payload: ReleaseQuotaRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Release unconsumed quota reservation."""
    qs = QuotaService(session)
    success = await qs.release_quota(payload.reservation_token)
    if not success:
        raise HTTPException(status_code=404, detail="Active reservation token not found")
    return {"status": "released", "reservation_token": payload.reservation_token}


@router.get("/usage")
async def get_user_usage(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Get active feature usage, pending reservations, and reset schedules."""
    qs = QuotaService(session)
    return await qs.get_user_usage_and_limits(user)


# ---------------------------------------------------------------------------
# Unit Economics & Compliance Audits
# ---------------------------------------------------------------------------

@router.get("/unit-economics")
async def get_unit_economics(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Inspect unit economics models, gross margins, and measured vs estimated costs."""
    svc = UnitEconomicsService(session)
    benchmarks = svc.get_benchmark_scenarios()
    measured = await svc.get_measured_vs_estimated_costs()
    return {
        "pricing_hypothesis": "$19/mo Pro (not fixed policy; modeled for fair margins)",
        "scenarios": benchmarks,
        "measured_telemetry": measured,
    }


@router.get("/provider-eligibility")
async def get_provider_eligibility() -> dict[str, Any]:
    """Audit India entity, RBI recurring payment regulations, and subscription provider readiness."""
    return IndiaEntityComplianceAudit.get_compliance_audit()


# ---------------------------------------------------------------------------
# Checkout & Portal
# ---------------------------------------------------------------------------

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CheckoutResponse:
    settings = get_settings()
    if not settings.stripe_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe checkout is disabled or not fully configured.",
        )
    try:
        import stripe
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail="stripe package is not installed") from exc

    stripe.api_key = settings.stripe_secret_key
    customer_id = user.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(
            email=user.email, metadata={"user_id": user.id}
        )
        customer_id = customer["id"]
        user.stripe_customer_id = customer_id
        session.add(user)
        await session.commit()

    checkout = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": settings.stripe_price_pro, "quantity": 1}],
        success_url=settings.stripe_success_url,
        cancel_url=settings.stripe_cancel_url,
        client_reference_id=user.id,
        metadata={"user_id": user.id},
    )
    return CheckoutResponse(url=checkout["url"], mode="stripe")


@router.post("/portal", response_model=CheckoutResponse)
async def create_portal(
    user: Annotated[User, Depends(get_current_user)],
) -> CheckoutResponse:
    settings = get_settings()
    if not settings.stripe_enabled:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer on this account")
    try:
        import stripe
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail="stripe package is not installed") from exc

    stripe.api_key = settings.stripe_secret_key
    portal = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=settings.public_app_url.rstrip("/") + "/preferences",
    )
    return CheckoutResponse(url=portal["url"], mode="portal")


@router.post("/dev-activate-pro", response_model=BillingStatus)
async def dev_activate_pro(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BillingStatus:
    """Local-only upgrade path when Stripe keys are not configured yet."""
    settings = get_settings()
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not found")
    user.plan = PLAN_PRO
    user.subscription_status = "dev"
    session.add(user)

    # Sync lifecycle record
    stmt = select(SubscriptionLifecycleRecord).where(SubscriptionLifecycleRecord.user_id == user.id)
    res = await session.execute(stmt)
    lifecycle = res.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if not lifecycle:
        lifecycle = SubscriptionLifecycleRecord(
            user_id=user.id,
            provider="mock_dev",
            plan=PLAN_PRO,
            status="dev",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            created_at=now,
            updated_at=now,
        )
        session.add(lifecycle)
    else:
        lifecycle.plan = PLAN_PRO
        lifecycle.status = "dev"
        lifecycle.updated_at = now

    await session.commit()
    await session.refresh(user)
    return await my_billing(user)


# ---------------------------------------------------------------------------
# Webhook Handler with Deduplication, Replay Defense, and Out-of-Order Check
# ---------------------------------------------------------------------------

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    settings = get_settings()
    if not settings.stripe_enabled:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    try:
        import stripe
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail="stripe package is not installed") from exc

    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=503,
            detail="STRIPE_WEBHOOK_SECRET is required. Unsigned Stripe webhooks are not accepted.",
        )

    payload = await request.body()
    signature = request.headers.get("stripe-signature")

    # 1. Replay timestamp window check from signature header
    if signature:
        for item in signature.split(","):
            if item.strip().startswith("t="):
                try:
                    t_val = int(item.strip().split("=")[1])
                    current_epoch = int(time.time())
                    if abs(current_epoch - t_val) > WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS:
                        raise HTTPException(
                            status_code=400,
                            detail="Webhook signature timestamp outside tolerance window (replay protection)",
                        )
                except ValueError:
                    pass

    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.stripe_webhook_secret
        )
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=f"Webhook verification failed: {exc}") from exc

    event_dict = event if isinstance(event, dict) else event.to_dict()
    event_id = event_dict.get("id", f"evt_{uuid4().hex}")
    event_type = event_dict.get("type", "unknown")
    event_created_raw = event_dict.get("created", int(time.time()))
    event_created = datetime.fromtimestamp(event_created_raw, timezone.utc)
    data_object = event_dict.get("data", {}).get("object", {})

    # 2. Event Deduplication check
    stmt_dedup = select(BillingWebhookEvent).where(BillingWebhookEvent.event_id == event_id)
    res_dedup = await session.execute(stmt_dedup)
    existing_event = res_dedup.scalar_one_or_none()
    if isinstance(existing_event, BillingWebhookEvent):
        return {"status": "duplicate_ignored", "event_id": event_id}

    payload_hash = hashlib.sha256(payload).hexdigest()
    webhook_log = BillingWebhookEvent(
        event_id=event_id,
        provider="stripe",
        event_type=event_type,
        status="processed",
        payload_hash=payload_hash,
        event_timestamp=event_created,
        processed_at=datetime.now(timezone.utc),
    )
    session.add(webhook_log)

    # 3. Apply subscription event with out-of-order check
    if event_type in {
        "checkout.session.completed",
        "customer.subscription.updated",
        "customer.subscription.created",
        "customer.subscription.resumed",
        "invoice.payment_succeeded",
    }:
        await _apply_subscription_event(session, data_object, event_timestamp=event_created, active=True)
    elif event_type in {"customer.subscription.deleted"}:
        await _apply_subscription_event(session, data_object, event_timestamp=event_created, active=False)
    elif event_type in {"invoice.payment_failed"}:
        await _apply_subscription_event(session, data_object, event_timestamp=event_created, active=False, past_due=True)

    await session.commit()
    return {"status": "ok"}


async def _apply_subscription_event(
    session: AsyncSession,
    data_object: dict,
    event_timestamp: datetime,
    *,
    active: bool,
    past_due: bool = False,
) -> None:
    user_id = None
    customer_id = data_object.get("customer")
    metadata = data_object.get("metadata") or {}
    if isinstance(metadata, dict):
        user_id = metadata.get("user_id")
    if not user_id:
        user_id = data_object.get("client_reference_id")

    user: User | None = None
    if user_id:
        result = await session.execute(select(User).where(User.id == str(user_id)))
        user = result.scalar_one_or_none()
    if user is None and customer_id:
        result = await session.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
    if user is None:
        return

    # Check for out-of-order event sequence via lifecycle record
    stmt_lc = select(SubscriptionLifecycleRecord).where(SubscriptionLifecycleRecord.user_id == user.id)
    res_lc = await session.execute(stmt_lc)
    lifecycle = res_lc.scalar_one_or_none()
    if not isinstance(lifecycle, SubscriptionLifecycleRecord):
        lifecycle = None

    if lifecycle and lifecycle.last_event_timestamp:
        last_ts = lifecycle.last_event_timestamp
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=timezone.utc)
        if event_timestamp < last_ts:
            # Out-of-order older event: do not overwrite newer state
            return

    now = datetime.now(timezone.utc)
    if customer_id:
        user.stripe_customer_id = customer_id
    subscription_id = data_object.get("subscription") or data_object.get("id")
    if isinstance(subscription_id, str) and subscription_id.startswith("sub_"):
        user.stripe_subscription_id = subscription_id

    status_value = data_object.get("status")

    if past_due or status_value == "past_due":
        user.plan = PLAN_FREE
        user.subscription_status = "past_due"
        target_status = "past_due"
        grace_until = now + timedelta(days=GRACE_PERIOD_DAYS)
    elif active and (
        status_value in {None, "active", "trialing"}
        or data_object.get("mode") == "subscription"
    ):
        user.plan = PLAN_PRO
        user.subscription_status = status_value or "active"
        target_status = user.subscription_status
        grace_until = None
    else:
        user.plan = PLAN_FREE
        user.subscription_status = status_value or "canceled"
        target_status = user.subscription_status
        grace_until = None

    # Sync lifecycle record
    if not lifecycle:
        lifecycle = SubscriptionLifecycleRecord(
            user_id=user.id,
            provider="stripe",
            customer_id=customer_id,
            subscription_id=subscription_id if isinstance(subscription_id, str) else None,
            plan=user.plan,
            status=target_status,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            grace_period_until=grace_until,
            last_event_timestamp=event_timestamp,
            created_at=now,
            updated_at=now,
        )
        session.add(lifecycle)
    else:
        lifecycle.plan = user.plan
        lifecycle.status = target_status
        lifecycle.customer_id = customer_id or lifecycle.customer_id
        lifecycle.subscription_id = (
            subscription_id if isinstance(subscription_id, str) else lifecycle.subscription_id
        )
        lifecycle.grace_period_until = grace_until
        lifecycle.last_event_timestamp = event_timestamp
        lifecycle.updated_at = now

    session.add(user)
