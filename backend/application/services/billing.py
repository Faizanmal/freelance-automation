from __future__ import annotations

from dataclasses import dataclass

from app.ingestion.sources import (
    COMMERCIAL_FREE_SOURCES,
    COMMERCIAL_PRO_SOURCES,
    MARKETPLACE_SOURCES,
    RESTRICTED_SOURCES,
)

from database.models.user import User

PLAN_FREE = "free"
PLAN_PRO = "pro"

FREE_SCRAPE_LIMIT = 15
PRO_SCRAPE_LIMIT = 100
FREE_MAX_DIGEST = 5
PRO_MAX_DIGEST = 25
FREE_DAILY_SCRAPE_RUNS = 3
PRO_DAILY_SCRAPE_RUNS = 50
FREE_CHANNELS = {"email"}
PRO_CHANNELS = {"email", "slack", "telegram", "discord", "whatsapp", "webhook"}


@dataclass(frozen=True, slots=True)
class PlanLimits:
    name: str
    scrape_limit: int
    max_digest: int
    daily_scrape_runs: int
    allowed_sources: tuple[str, ...]
    allowed_channels: frozenset[str]
    marketplace: bool
    price_label: str
    features: tuple[str, ...]


PLANS: dict[str, PlanLimits] = {
    PLAN_FREE: PlanLimits(
        name=PLAN_FREE,
        scrape_limit=FREE_SCRAPE_LIMIT,
        max_digest=FREE_MAX_DIGEST,
        daily_scrape_runs=FREE_DAILY_SCRAPE_RUNS,
        allowed_sources=COMMERCIAL_FREE_SOURCES,
        allowed_channels=frozenset(FREE_CHANNELS),
        marketplace=False,
        price_label="$0",
        features=(
            "Hunt Rules, ranked Leads, Save/Skip",
            "V1 hunters (SerpAPI/Tavily spine) + free boards",
            f"Email digest up to {FREE_MAX_DIGEST} leads",
            f"Up to {FREE_SCRAPE_LIMIT} jobs per manual hunt",
            f"{FREE_DAILY_SCRAPE_RUNS} manual hunts per day",
            "Proposal draft starter",
        ),
    ),
    PLAN_PRO: PlanLimits(
        name=PLAN_PRO,
        scrape_limit=PRO_SCRAPE_LIMIT,
        max_digest=PRO_MAX_DIGEST,
        daily_scrape_runs=PRO_DAILY_SCRAPE_RUNS,
        allowed_sources=COMMERCIAL_PRO_SOURCES,
        allowed_channels=frozenset(PRO_CHANNELS),
        marketplace=True,
        price_label="$19/mo",
        features=(
            "Everything in Free",
            f"Higher hunt density — up to {PRO_SCRAPE_LIMIT} jobs per hunt",
            f"Email digest up to {PRO_MAX_DIGEST} leads",
            f"{PRO_DAILY_SCRAPE_RUNS} manual hunts per day",
            "Google Maps / local discovery (serpapi_maps)",
            "Slack, Telegram, Discord, WhatsApp alerts",
            "Optional marketplace APIs when you enable them",
        ),
    ),
}


def normalize_plan(plan: str | None) -> str:
    value = (plan or PLAN_FREE).strip().lower()
    return value if value in PLANS else PLAN_FREE


def is_pro(user: User) -> bool:
    if normalize_plan(user.plan) != PLAN_PRO:
        return False
    status = (user.subscription_status or "active").lower()
    # past_due keeps the Stripe subscription id but does not unlock Pro features.
    return status in {"active", "trialing", "dev"}


def limits_for_user(user: User) -> PlanLimits:
    return PLANS[PLAN_PRO if is_pro(user) else PLAN_FREE]


def clamp_digest_limit(user: User, requested: int | None) -> int:
    """Clamp max_per_digest to the user's plan ceiling."""
    plan = limits_for_user(user)
    value = int(requested if requested is not None else plan.max_digest)
    return max(1, min(value, plan.max_digest))


def filter_sources_for_user(user: User, sources: list[str]) -> list[str]:
    allowed = set(limits_for_user(user).allowed_sources)
    return [source for source in sources if source in allowed]


def blocked_restricted_sources(sources: list[str]) -> list[str]:
    restricted = set(RESTRICTED_SOURCES)
    return [source for source in sources if source in restricted]


def filter_channels_for_user(user: User, channels: list[str]) -> list[str]:
    allowed = limits_for_user(user).allowed_channels
    return [channel for channel in channels if channel in allowed]


def destinations_from_preferences(prefs) -> dict[str, str]:
    return {
        key: value
        for key, value in {
            "email": prefs.alert_email,
            "slack_webhook_url": prefs.slack_webhook_url,
            "telegram_chat_id": prefs.telegram_chat_id,
            "discord_webhook_url": prefs.discord_webhook_url,
            "whatsapp_to": prefs.whatsapp_to,
            "custom_webhook_url": getattr(prefs, "custom_webhook_url", None),
        }.items()
        if value
    }


def marketplace_sources() -> tuple[str, ...]:
    return MARKETPLACE_SOURCES
