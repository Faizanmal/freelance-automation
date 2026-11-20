"""Typed source registry: permissions, attribution, budgets, health policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from app.ingestion.sources import (
    COMMERCIAL_FREE_SOURCES,
    COMMERCIAL_PRO_SOURCES,
    DIRECT_ATS_SOURCES,
    DISCOVERY_SOURCES,
    EXPERIMENTAL_BROWSER_SOURCES,
    MARKETPLACE_SOURCES,
    POST_V1_HUNTERS,
    PUBLIC_SOURCES,
    RESTRICTED_SOURCES,
    SOURCE_ATTRIBUTION,
    SOURCE_REGISTRY,
    V1_DEFAULT_HUNTERS,
)

PermissionState = Literal[
    "authorized",
    "conditional",
    "restricted",
    "experimental",
    "disabled",
]
SourceCategory = Literal[
    "search",
    "ats",
    "board",
    "community",
    "marketplace",
    "browser",
]
CheckpointStrategy = Literal["none", "cursor", "page", "timestamp", "cache_key"]


@dataclass(slots=True)
class SourcePolicy:
    key: str
    display_name: str
    category: SourceCategory
    permission: PermissionState
    enabled_by_default: bool
    requires_credentials: tuple[str, ...]
    rate_limit_per_hour: int | None
    daily_budget_usd: float | None
    attribution: str
    allowed_fields: tuple[str, ...]
    ttl_days: int
    checkpoint: CheckpointStrategy
    retention_days_raw: int
    notes: str
    commercial_plans: tuple[str, ...] = ()
    max_concurrency: int = 1
    last_success_at: datetime | None = None
    health: str = "unknown"
    operator_disabled: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "display_name": self.display_name,
            "category": self.category,
            "permission": self.permission,
            "enabled_by_default": self.enabled_by_default,
            "requires_credentials": list(self.requires_credentials),
            "rate_limit_per_hour": self.rate_limit_per_hour,
            "daily_budget_usd": self.daily_budget_usd,
            "attribution": self.attribution,
            "allowed_fields": list(self.allowed_fields),
            "ttl_days": self.ttl_days,
            "checkpoint": self.checkpoint,
            "retention_days_raw": self.retention_days_raw,
            "notes": self.notes,
            "commercial_plans": list(self.commercial_plans),
            "max_concurrency": self.max_concurrency,
            "last_success_at": (
                self.last_success_at.isoformat() if self.last_success_at else None
            ),
            "health": self.health,
            "operator_disabled": self.operator_disabled,
            "adapter_registered": self.key in SOURCE_REGISTRY,
        }


_COMMON_FIELDS = (
    "source_id",
    "title",
    "description",
    "url",
    "company",
    "location",
    "tags",
    "posted_at",
)
_COMP_FIELDS = _COMMON_FIELDS + ("budget_min", "budget_max")


def _category_for(key: str) -> SourceCategory:
    if key in DISCOVERY_SOURCES:
        return "search"
    if key in DIRECT_ATS_SOURCES:
        return "ats"
    if key in MARKETPLACE_SOURCES:
        return "marketplace"
    if key in EXPERIMENTAL_BROWSER_SOURCES:
        return "browser"
    if key in POST_V1_HUNTERS:
        return "community"
    return "board"


def _permission_for(key: str) -> PermissionState:
    if key in RESTRICTED_SOURCES:
        return "restricted"
    if key in EXPERIMENTAL_BROWSER_SOURCES:
        return "experimental"
    if key in MARKETPLACE_SOURCES:
        return "conditional"
    if key in DISCOVERY_SOURCES or key in POST_V1_HUNTERS:
        return "conditional"
    if key in PUBLIC_SOURCES or key in DIRECT_ATS_SOURCES:
        return "authorized"
    return "disabled"


def _credentials_for(key: str) -> tuple[str, ...]:
    if key.startswith("serpapi_"):
        return ("TAVILY_API_KEY|SERPAPI_API_KEY",)
    if key == "upwork":
        return ("UPWORK_CLIENT_ID", "UPWORK_CLIENT_SECRET")
    if key == "freelancer":
        return ("FREELANCER_API_TOKEN",)
    if key in {"peopleperhour", "guru"}:
        return ("APIFY_API_TOKEN",)
    if key == "reddit_hiring":
        return ("REDDIT_CLIENT_ID|public_json",)
    return ()


def _rate_for(key: str) -> int | None:
    if key.startswith("serpapi_"):
        return 30
    if key in MARKETPLACE_SOURCES:
        return 20
    if key in DIRECT_ATS_SOURCES:
        return 60
    if key in POST_V1_HUNTERS:
        return 12
    return 40


def _budget_for(key: str) -> float | None:
    if key.startswith("serpapi_"):
        return 5.0
    if key in {"peopleperhour", "guru"}:
        return 3.0
    return 0.0


def _ttl_for(key: str) -> int:
    from backend.application.services.job_expiration import SOURCE_TTL_DAYS

    return int(SOURCE_TTL_DAYS.get(key, 45))


def _checkpoint_for(key: str) -> CheckpointStrategy:
    if key.startswith("serpapi_"):
        return "cache_key"
    if key in DIRECT_ATS_SOURCES:
        return "page"
    if key in POST_V1_HUNTERS:
        return "timestamp"
    return "none"


def _plans_for(key: str) -> tuple[str, ...]:
    if key in COMMERCIAL_PRO_SOURCES and key not in COMMERCIAL_FREE_SOURCES:
        return ("pro",)
    if key in COMMERCIAL_FREE_SOURCES:
        return ("free", "pro")
    return ()


def build_source_policy(key: str) -> SourcePolicy:
    permission = _permission_for(key)
    enabled = (
        permission == "authorized"
        or key in V1_DEFAULT_HUNTERS
        or key in DIRECT_ATS_SOURCES
    ) and permission not in {"restricted", "experimental", "disabled"}
    # Conditional V1 hunters enabled by default when keyed at runtime (gate checks creds).
    if key in V1_DEFAULT_HUNTERS:
        enabled = True
    if permission in {"restricted", "experimental"}:
        enabled = False
    return SourcePolicy(
        key=key,
        display_name=SOURCE_ATTRIBUTION.get(key, key),
        category=_category_for(key),
        permission=permission,
        enabled_by_default=enabled,
        requires_credentials=_credentials_for(key),
        rate_limit_per_hour=_rate_for(key),
        daily_budget_usd=_budget_for(key),
        attribution=SOURCE_ATTRIBUTION.get(key, key),
        allowed_fields=_COMP_FIELDS if key in PUBLIC_SOURCES else _COMMON_FIELDS,
        ttl_days=_ttl_for(key),
        checkpoint=_checkpoint_for(key),
        retention_days_raw=14 if permission != "restricted" else 0,
        notes=_notes_for(key, permission),
        commercial_plans=_plans_for(key),
        max_concurrency=1,
    )


def _notes_for(key: str, permission: PermissionState) -> str:
    if permission == "restricted":
        return (
            "Registered for demos only. Blocked from commercial scrapes until "
            "written commercial permission exists. Do not bypass ToS/paywalls."
        )
    if permission == "experimental":
        return (
            "Browser/Playwright path needs authenticated sessions; not sold. "
            "Default-disabled."
        )
    if key.startswith("serpapi_"):
        return (
            "Permitted search providers (Tavily primary, SerpAPI fallback). "
            "Shared cache + per-source lease; capped concurrency."
        )
    if key in DIRECT_ATS_SOURCES:
        return "Official ATS job board APIs / public feeds where available."
    if key in MARKETPLACE_SOURCES:
        return "Requires API credentials and Pro plan; never scrape authenticated HTML."
    return "Public board or community feed under published terms."


# Runtime operator overrides (in-memory; Redis-backed when available via reliability).
_OPERATOR_DISABLED: set[str] = set()
_HEALTH_CACHE: dict[str, dict[str, Any]] = {}


def set_operator_disabled(key: str, disabled: bool) -> None:
    if disabled:
        _OPERATOR_DISABLED.add(key)
    else:
        _OPERATOR_DISABLED.discard(key)


def is_operator_disabled(key: str) -> bool:
    return key in _OPERATOR_DISABLED


def record_source_health(
    key: str,
    *,
    ok: bool,
    detail: str | None = None,
    fetched: int | None = None,
) -> None:
    _HEALTH_CACHE[key] = {
        "ok": ok,
        "detail": detail,
        "fetched": fetched,
        "at": datetime.now(UTC).isoformat(),
    }


def get_typed_registry() -> dict[str, SourcePolicy]:
    policies: dict[str, SourcePolicy] = {}
    for key in SOURCE_REGISTRY:
        policy = build_source_policy(key)
        policy.operator_disabled = is_operator_disabled(key)
        health = _HEALTH_CACHE.get(key)
        if health:
            policy.health = "healthy" if health.get("ok") else "degraded"
            try:
                policy.last_success_at = (
                    datetime.fromisoformat(str(health["at"]))
                    if health.get("ok")
                    else None
                )
            except ValueError:
                policy.last_success_at = None
        policies[key] = policy
    return policies


def list_policies(*, include_disabled: bool = True) -> list[SourcePolicy]:
    rows = list(get_typed_registry().values())
    if not include_disabled:
        rows = [
            p
            for p in rows
            if p.enabled_by_default
            and not p.operator_disabled
            and p.permission not in {"restricted", "disabled"}
        ]
    return sorted(rows, key=lambda p: p.key)


def governance_audit_summary() -> dict[str, Any]:
    policies = list_policies(include_disabled=True)
    by_perm: dict[str, list[str]] = {}
    for p in policies:
        by_perm.setdefault(p.permission, []).append(p.key)
    return {
        "adapter_count": len(SOURCE_REGISTRY),
        "policy_count": len(policies),
        "by_permission": {k: sorted(v) for k, v in by_perm.items()},
        "default_enabled": sorted(
            p.key for p in policies if p.enabled_by_default and not p.operator_disabled
        ),
        "restricted_default_off": sorted(RESTRICTED_SOURCES),
        "experimental_default_off": sorted(EXPERIMENTAL_BROWSER_SOURCES),
        "v1_hunters": list(V1_DEFAULT_HUNTERS),
        "product_boundary": (
            "Shared inventory + hunt rules only. Ranking and digest scheduling "
            "remain user-specific and outside ingestion."
        ),
        "compliance": {
            "no_paywall_bypass": True,
            "no_captcha_bypass": True,
            "honor_rate_limits": True,
            "prefer_official_apis": True,
            "nulls_not_fabrications": True,
        },
    }
