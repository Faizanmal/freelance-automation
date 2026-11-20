"""Source policy gate — blocks unauthorized/disabled sources before fetch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ingestion.governance import (
    SourcePolicy,
    get_typed_registry,
    is_operator_disabled,
)
from app.ingestion.sources import SOURCE_REGISTRY, V1_DEFAULT_HUNTERS
from config.settings import get_settings


@dataclass(slots=True)
class GateDecision:
    allowed: bool
    reason: str
    policy: SourcePolicy | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "policy": self.policy.to_dict() if self.policy else None,
        }


def _credentials_present(policy: SourcePolicy) -> bool:
    settings = get_settings()
    for req in policy.requires_credentials:
        # Support "A|B" meaning either credential.
        alts = [part.strip() for part in req.split("|")]
        ok = False
        for alt in alts:
            if alt == "public_json":
                ok = True
                break
            attr = alt.lower()
            if hasattr(settings, attr) and getattr(settings, attr):
                ok = True
                break
            # Common settings aliases
            if alt == "TAVILY_API_KEY" and getattr(settings, "tavily_api_key", None):
                ok = True
                break
            if alt == "SERPAPI_API_KEY" and getattr(settings, "serpapi_api_key", None):
                ok = True
                break
            if alt == "UPWORK_CLIENT_ID" and getattr(settings, "upwork_client_id", None):
                ok = True
                break
            if alt == "UPWORK_CLIENT_SECRET" and getattr(
                settings, "upwork_client_secret", None
            ):
                ok = True
                break
            if alt == "FREELANCER_API_TOKEN" and getattr(
                settings, "freelancer_api_token", None
            ):
                ok = True
                break
            if alt == "APIFY_API_TOKEN" and getattr(settings, "apify_api_token", None):
                ok = True
                break
            if alt == "REDDIT_CLIENT_ID" and getattr(settings, "reddit_client_id", None):
                ok = True
                break
        if not ok:
            return False
    return True


def evaluate_source(
    source_name: str,
    *,
    explicit_allowlist: list[str] | None = None,
    require_default_enabled: bool = False,
) -> GateDecision:
    registry = get_typed_registry()
    policy = registry.get(source_name)
    if policy is None or source_name not in SOURCE_REGISTRY:
        return GateDecision(False, "unknown_source")

    if is_operator_disabled(source_name) or policy.operator_disabled:
        return GateDecision(False, "operator_disabled", policy)

    if policy.permission == "restricted":
        # Only allow when explicitly listed AND settings opt-in flag if present.
        allow_restricted = bool(
            getattr(get_settings(), "allow_restricted_sources", False)
        )
        if not allow_restricted:
            return GateDecision(False, "restricted_licensing", policy)

    if policy.permission == "experimental":
        if not getattr(get_settings(), "allow_browser_sources", False):
            return GateDecision(False, "experimental_disabled", policy)

    if policy.permission == "disabled":
        return GateDecision(False, "disabled", policy)

    if require_default_enabled and not policy.enabled_by_default:
        if explicit_allowlist is None or source_name not in explicit_allowlist:
            return GateDecision(False, "not_default_enabled", policy)

    if policy.requires_credentials and not _credentials_present(policy):
        # Still allow board sources with empty credential list; conditional need keys.
        if policy.permission == "conditional":
            return GateDecision(False, "missing_credentials", policy)

    return GateDecision(True, "ok", policy)


def filter_sources(
    requested: list[str] | None,
    *,
    default: list[str] | None = None,
) -> tuple[list[str], dict[str, GateDecision]]:
    """
    Apply policy gate to a requested source list.
    Defaults to V1 hunters when none provided.
    """
    selected = list(requested or default or list(V1_DEFAULT_HUNTERS))
    settings_list = get_settings().scrape_source_list
    decisions: dict[str, GateDecision] = {}
    allowed: list[str] = []
    for name in selected:
        decision = evaluate_source(
            name,
            explicit_allowlist=settings_list or selected,
            require_default_enabled=False,
        )
        decisions[name] = decision
        if decision.allowed:
            allowed.append(name)
    return allowed, decisions
