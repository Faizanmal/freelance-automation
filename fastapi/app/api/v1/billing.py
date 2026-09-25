from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from config.settings import get_settings
from database.core.session import get_db
from database.models.user import User
from backend.application.services.billing import PLAN_FREE, PLAN_PRO, PLANS, is_pro, limits_for_user, normalize_plan

router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutResponse(BaseModel):
    url: str
    mode: str


class BillingStatus(BaseModel):
    plan: str
    subscription_status: str
    is_pro: bool
    stripe_enabled: bool
    limits: dict[str, object]
    features: list[str]


@router.get("/plans")
async def list_plans() -> dict[str, object]:
    settings = get_settings()
    return {
        "stripe_enabled": settings.stripe_enabled,
        "plans": [
            {
                "id": plan.name,
                "price_label": plan.price_label,
                "marketplace": plan.marketplace,
                "scrape_limit": plan.scrape_limit,
                "channels": sorted(plan.allowed_channels),
                "features": list(plan.features),
            }
            for plan in PLANS.values()
        ],
    }


@router.get("/me", response_model=BillingStatus)
async def my_billing(user: User = Depends(get_current_user)) -> BillingStatus:
    settings = get_settings()
    limits = limits_for_user(user)
    return BillingStatus(
        plan=normalize_plan(user.plan),
        subscription_status=user.subscription_status or "inactive",
        is_pro=is_pro(user),
        stripe_enabled=settings.stripe_enabled,
        limits={
            "scrape_limit": limits.scrape_limit,
            "marketplace": limits.marketplace,
            "channels": sorted(limits.allowed_channels),
            "sources": list(limits.allowed_sources),
        },
        features=list(limits.features),
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CheckoutResponse:
    settings = get_settings()
    if not settings.stripe_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured. Set STRIPE_SECRET_KEY and STRIPE_PRICE_PRO.",
        )
    try:
        import stripe
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail="stripe package is not installed") from exc

    stripe.api_key = settings.stripe_secret_key
    customer_id = user.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(email=user.email, metadata={"user_id": user.id})
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
    user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> BillingStatus:
    """Local-only upgrade path when Stripe keys are not configured yet."""
    settings = get_settings()
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not found")
    user.plan = PLAN_PRO
    user.subscription_status = "dev"
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return await my_billing(user)


@router.post("/webhook")
async def stripe_webhook(request: Request, session: AsyncSession = Depends(get_db)) -> dict[str, str]:
    settings = get_settings()
    if not settings.stripe_enabled:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    try:
        import stripe
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail="stripe package is not installed") from exc

    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    if settings.stripe_webhook_secret:
        try:
            event = stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Webhook verification failed: {exc}") from exc
    else:
        import json

        event = json.loads(payload)

    event_type = event["type"] if isinstance(event, dict) else event.type
    data_object = event["data"]["object"] if isinstance(event, dict) else event.data.object

    if event_type in {"checkout.session.completed", "customer.subscription.updated", "customer.subscription.created"}:
        await _apply_subscription_event(session, data_object, active=True)
    elif event_type in {"customer.subscription.deleted"}:
        await _apply_subscription_event(session, data_object, active=False)

    return {"status": "ok"}


async def _apply_subscription_event(session: AsyncSession, data_object: dict, *, active: bool) -> None:
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
        result = await session.execute(select(User).where(User.stripe_customer_id == customer_id))
        user = result.scalar_one_or_none()
    if user is None:
        return

    if customer_id:
        user.stripe_customer_id = customer_id
    subscription_id = data_object.get("subscription") or data_object.get("id")
    if isinstance(subscription_id, str) and subscription_id.startswith("sub_"):
        user.stripe_subscription_id = subscription_id

    status_value = data_object.get("status")
    if active and (status_value in {None, "active", "trialing"} or data_object.get("mode") == "subscription"):
        user.plan = PLAN_PRO
        user.subscription_status = status_value or "active"
    else:
        user.plan = PLAN_FREE
        user.subscription_status = status_value or "canceled"

    session.add(user)
    await session.commit()
