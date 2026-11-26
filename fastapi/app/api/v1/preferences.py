from __future__ import annotations

from typing import Annotated, Any, Literal
import random
import urllib.parse

from app.api.dependencies import get_current_user
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.billing import (
    clamp_digest_limit,
    filter_channels_for_user,
    is_pro,
)
from backend.application.services.digest_scheduler import validate_iana_timezone
from backend.application.services.lead_findings import LeadFindingsService
from backend.application.services.match_feedback import MatchFeedbackService
from backend.application.services.matching import MatchingService
from backend.application.services.notification_service import (
    CustomWebhookAdapter,
    NotificationChannel,
    NotificationEnvelope,
    NotificationPriority,
)
from backend.application.services.ranking.cache import (
    get_recommendation_cache,
    recommendation_cache_key,
)
from backend.application.services.ranking.embeddings import EmbeddingIndex
from backend.application.services.ranking.pipeline import RankingPipeline
from backend.application.services.ranking.profile import RANKING_CONSENT_PURPOSE
from backend.infrastructure.repositories.job_repository import SQLAlchemyJobRepository
from database.core.session import get_db
from database.models.application import JobApplication
from database.models.job import JobRecord
from database.models.lead_action import UserLeadAction
from database.models.preference import UserPreferences
from database.models.user import User
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/preferences", tags=["preferences"])


ExperienceLevel = Literal["any", "junior", "mid", "senior", "lead"]


async def _bump_jobs_cache_epoch() -> None:
    """Invalidate list/count caches so Desk, /leads and /freelance-jobs agree."""
    try:
        from app.core.redis_client import get_redis

        redis_client = await get_redis()
        if redis_client:
            await redis_client.incr("jobs_cache:epoch")
    except Exception:
        pass


_PURGE_PAGE_TYPES = frozenset(
    {
        "listicle",
        "board_index",
        "careers_hub",
        "portfolio",
        "spam_host",
        "non_dev",
        "full_time_employee",
    }
)


async def _purge_non_opportunity_jobs(
    session: AsyncSession,
    jobs: list[JobRecord],
    *,
    persist: bool = True,
) -> list[JobRecord]:
    """Drop listicles/boards/hubs/FTE-noise from a candidate set.

    When persist=True, only expire high-confidence noise (never job_post).
    Demo/unauth paths should pass persist=False so browsing does not shrink the index.
    """
    import logging
    from datetime import datetime, timezone

    from backend.application.services.page_type import (
        ALWAYS_NOISE_HOSTS,
        classify_page_type,
        is_non_opportunity_noise,
    )
    from sqlalchemy import or_

    log = logging.getLogger("signaldesk.purge")
    changed = False
    keep: list[JobRecord] = []
    now = datetime.now(timezone.utc)
    seen_ids: set[int] = set()
    purged: list[dict[str, Any]] = []

    for job in jobs:
        if getattr(job, "is_expired", False):
            continue
        enrichment = getattr(job, "enrichment", None)
        enrichment_dict = enrichment if isinstance(enrichment, dict) else None
        page_type = classify_page_type(
            job.title,
            job.description,
            job.url,
            job.company,
            enrichment=enrichment_dict,
        )
        noise = page_type in _PURGE_PAGE_TYPES and is_non_opportunity_noise(
            job.title,
            job.description,
            job.url,
            job.company,
            enrichment=enrichment_dict,
        )
        if noise:
            purged.append(
                {
                    "job_id": job.id,
                    "title": (job.title or "")[:120],
                    "url": job.url,
                    "page_type": page_type,
                }
            )
            if persist:
                job.is_expired = True
                job.expired_reason = f"non_opportunity_noise:{page_type}"
                job.expired_at = now
                session.add(job)
                changed = True
            if job.id is not None:
                seen_ids.add(job.id)
            continue
        keep.append(job)

    if persist:
        # Expire always-noise hosts already stored outside the candidate window.
        host_clauses = [
            JobRecord.url.ilike(f"%{host}%") for host in ALWAYS_NOISE_HOSTS
        ]
        if host_clauses:
            result = await session.execute(
                select(JobRecord).where(
                    JobRecord.is_expired.is_(False),
                    or_(*host_clauses),
                ).limit(500)
            )
            for job in result.scalars().all():
                if job.id in seen_ids:
                    continue
                enrichment = getattr(job, "enrichment", None)
                page_type = classify_page_type(
                    job.title,
                    job.description,
                    job.url,
                    job.company,
                    enrichment=enrichment if isinstance(enrichment, dict) else None,
                )
                # Spot-check: only expire if classifier still agrees.
                if page_type not in _PURGE_PAGE_TYPES and page_type != "listicle":
                    # Host is denylisted but this URL classified as a real post — keep.
                    log.info(
                        "purge_skip_false_positive job_id=%s host_denylist page_type=%s title=%r",
                        job.id,
                        page_type,
                        (job.title or "")[:80],
                    )
                    continue
                job.is_expired = True
                job.expired_reason = f"non_opportunity_noise:{page_type or 'denylist_host'}"
                job.expired_at = now
                session.add(job)
                changed = True
                purged.append(
                    {
                        "job_id": job.id,
                        "title": (job.title or "")[:120],
                        "url": job.url,
                        "page_type": page_type or "denylist_host",
                    }
                )

    if purged:
        log.info(
            "purge_summary persist=%s count=%s samples=%s",
            persist,
            len(purged),
            purged[:15],
        )

    if changed:
        await session.commit()
        get_recommendation_cache().invalidate_prefix()
        await _bump_jobs_cache_epoch()
    return keep


async def _archive_noise_lead_actions(
    session: AsyncSession, user_id: str
) -> int:
    """Soft-delete accidental Saves of clear board/listicle noise only.

    Never touches pitched/won/skip. Not called from GET /findings or
    /pipeline-stats (those races wiped optimistic Save/Undo).
    """
    from datetime import datetime, timezone

    from backend.application.services.page_type import (
        PAGE_TYPE_BOARD_INDEX,
        PAGE_TYPE_CAREERS_HUB,
        PAGE_TYPE_LISTICLE,
        PAGE_TYPE_SPAM_HOST,
        classify_page_type,
        is_non_opportunity_noise,
    )

    result = await session.execute(
        select(UserLeadAction, JobRecord)
        .outerjoin(JobRecord, UserLeadAction.job_id == JobRecord.id)
        .where(
            UserLeadAction.user_id == user_id,
            UserLeadAction.deleted_at.is_(None),
            UserLeadAction.status == "save",
        )
    )
    hub_types = {
        PAGE_TYPE_LISTICLE,
        PAGE_TYPE_BOARD_INDEX,
        PAGE_TYPE_CAREERS_HUB,
        PAGE_TYPE_SPAM_HOST,
    }
    archived = 0
    now = datetime.now(timezone.utc)
    for action, job in result.all():
        if job is None:
            continue
        title = getattr(job, "title", None)
        description = getattr(job, "description", None)
        url = getattr(job, "url", None)
        company = getattr(job, "company", None)
        enrichment = getattr(job, "enrichment", None)
        enrichment_dict = enrichment if isinstance(enrichment, dict) else None
        page_type = classify_page_type(
            title,
            description,
            url,
            company,
            enrichment=enrichment_dict,
        )
        if page_type not in hub_types:
            continue
        if not is_non_opportunity_noise(
            title,
            description,
            url,
            company,
            enrichment=enrichment_dict,
        ):
            continue
        action.deleted_at = now
        action.pipeline_stage = "archived"
        action.reason = action.reason or f"auto_archive_noise:{page_type}"
        session.add(action)
        archived += 1
    if archived:
        await session.commit()
        get_recommendation_cache().invalidate_user(str(user_id))
    return archived


class PreferencesPayload(BaseModel):
    keywords: list[str] = Field(
        default_factory=list, max_length=40
    )
    exclude_keywords: list[str] = Field(default_factory=list, max_length=40)
    skills: list[str] = Field(
        default_factory=lambda: ["python", "fastapi", "react"], max_length=40
    )
    experience_level: ExperienceLevel = "any"
    min_budget: float | None = None
    max_budget: float | None = None
    min_hourly_rate: float | None = None
    sources: list[str] = Field(default_factory=list, max_length=20)
    match_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    notification_channels: list[str] = Field(
        default_factory=lambda: ["email"], max_length=10
    )
    digest_mode: bool = True
    freelance_focus: bool = True
    hide_agency_leads: bool = False
    location: str | None = Field(default=None, max_length=128)
    timezone: str | None = Field(default=None, max_length=64)
    digest_days: list[str] | None = Field(default=None, max_length=7)
    digest_time_local: str | None = Field(default=None, max_length=8)
    max_per_digest: int = Field(default=5, ge=1, le=50)
    notes: str | None = Field(default=None, max_length=2000)
    alert_email: EmailStr | None = None
    slack_webhook_url: str | None = Field(default=None, max_length=1024)
    telegram_chat_id: str | None = Field(default=None, max_length=128)
    discord_webhook_url: str | None = Field(default=None, max_length=1024)
    whatsapp_to: str | None = Field(default=None, max_length=64)
    custom_webhook_url: str | None = Field(default=None, max_length=1024)
    cadence: str = Field(default="daily", max_length=32)
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = Field(default="22:00", max_length=8)
    quiet_hours_end: str = Field(default="08:00", max_length=8)
    event_types: list[str] = Field(
        default_factory=lambda: ["lead_match", "digest", "immediate_alert"]
    )
    is_paused: bool = False
    is_unsubscribed: bool = False
    empty_digest_policy: str = Field(default="suppress", max_length=32)
    immediate_alerts_enabled: bool = True
    immediate_alert_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    immediate_alert_cap_per_day: int = Field(default=5, ge=1, le=50)


class PreferencesOut(PreferencesPayload):
    id: int
    user_id: str


class LeadActionPayload(BaseModel):
    status: Literal["save", "skip", "pitched", "won", "clear"]
    reason: str | None = Field(default=None, max_length=64)
    feedback_kind: str | None = Field(default=None, max_length=32)
    write_version: int | None = Field(default=None, ge=0)
    client_ts: int | None = Field(default=None, ge=0)
    # Why? chip after Save/Skip — must not revive a soft-deleted Unsave/Undo.
    reason_only: bool = False


class MatchFeedbackPayload(BaseModel):
    job_id: int
    kind: Literal[
        "save",
        "skip",
        "hide_source",
        "apply_click",
        "outcome",
        "clear",
    ]
    reason: str | None = Field(default=None, max_length=64)
    outcome: Literal["interview", "contract", "rejected", "none"] | None = None
    write_version: int | None = Field(default=None, ge=0)
    client_ts: int | None = Field(default=None, ge=0)


async def _lead_status_sets(
    session: AsyncSession, user_id: str
) -> tuple[set[int], set[int]]:
    result = await session.execute(
        select(UserLeadAction).where(
            UserLeadAction.user_id == user_id,
            UserLeadAction.deleted_at.is_(None),
        )
    )
    skipped: set[int] = set()
    saved: set[int] = set()
    for row in result.scalars().all():
        if row.status == "skip":
            skipped.add(row.job_id)
        elif row.status == "save":
            saved.add(row.job_id)
    return skipped, saved


def _normalize_experience(value: str | None) -> ExperienceLevel:
    raw = (value or "any").strip().lower()
    if raw in {"any", "junior", "mid", "senior", "lead"}:
        return raw  # type: ignore[return-value]
    return "any"


def _prefs_out(prefs: UserPreferences) -> PreferencesOut:
    skills = list(getattr(prefs, "skills", None) or [])
    keywords = list(prefs.keywords or [])
    # Legacy rows: surface keywords as skills when skills were never set.
    if not skills and keywords:
        skills = list(keywords)
    return PreferencesOut(
        id=prefs.id,
        user_id=prefs.user_id,
        keywords=keywords,
        exclude_keywords=prefs.exclude_keywords or [],
        skills=skills,
        experience_level=_normalize_experience(
            getattr(prefs, "experience_level", None)
        ),
        min_budget=prefs.min_budget,
        max_budget=prefs.max_budget,
        min_hourly_rate=getattr(prefs, "min_hourly_rate", None),
        sources=prefs.sources or [],
        match_threshold=prefs.match_threshold,
        notification_channels=prefs.notification_channels or [],
        digest_mode=bool(prefs.digest_mode),
        freelance_focus=bool(getattr(prefs, "freelance_focus", True)),
        hide_agency_leads=bool(getattr(prefs, "hide_agency_leads", False)),
        location=getattr(prefs, "location", None),
        timezone=getattr(prefs, "timezone", None),
        digest_days=(
            list(prefs.digest_days) if getattr(prefs, "digest_days", None) else None
        ),
        digest_time_local=getattr(prefs, "digest_time_local", None),
        max_per_digest=int(getattr(prefs, "max_per_digest", None) or 5),
        notes=prefs.notes,
        alert_email=prefs.alert_email,
        slack_webhook_url=prefs.slack_webhook_url,
        telegram_chat_id=prefs.telegram_chat_id,
        discord_webhook_url=prefs.discord_webhook_url,
        whatsapp_to=prefs.whatsapp_to,
        custom_webhook_url=getattr(prefs, "custom_webhook_url", None),
        cadence=getattr(prefs, "cadence", "daily") or "daily",
        quiet_hours_enabled=bool(getattr(prefs, "quiet_hours_enabled", False)),
        quiet_hours_start=getattr(prefs, "quiet_hours_start", "22:00") or "22:00",
        quiet_hours_end=getattr(prefs, "quiet_hours_end", "08:00") or "08:00",
        event_types=list(
            getattr(prefs, "event_types", None)
            or ["lead_match", "digest", "immediate_alert"]
        ),
        is_paused=bool(getattr(prefs, "is_paused", False)),
        is_unsubscribed=bool(getattr(prefs, "is_unsubscribed", False)),
        empty_digest_policy=getattr(prefs, "empty_digest_policy", "suppress")
        or "suppress",
        immediate_alerts_enabled=bool(
            getattr(prefs, "immediate_alerts_enabled", True)
        ),
        immediate_alert_threshold=float(
            getattr(prefs, "immediate_alert_threshold", 0.85) or 0.85
        ),
        immediate_alert_cap_per_day=int(
            getattr(prefs, "immediate_alert_cap_per_day", 5) or 5
        ),
    )


async def _get_or_create_preferences(
    session: AsyncSession, user: User
) -> UserPreferences:
    result = await session.execute(
        select(UserPreferences).where(UserPreferences.user_id == user.id)
    )
    prefs = result.scalar_one_or_none()
    if prefs:
        return prefs
    prefs = UserPreferences(
        user_id=user.id,
        keywords=[],
        exclude_keywords=[],
        skills=["python", "fastapi", "react", "typescript"],
        experience_level="any",
        sources=[],
        notification_channels=["email"],
        match_threshold=0.35,
        digest_mode=True,
        freelance_focus=True,
        hide_agency_leads=False,
        digest_days=["mon", "tue", "wed", "thu", "fri"],
        digest_time_local="09:00",
        max_per_digest=5,
        alert_email=user.email,
    )
    session.add(prefs)
    await session.commit()
    await session.refresh(prefs)
    return prefs


@router.get("/me", response_model=PreferencesOut)
async def get_my_preferences(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PreferencesOut:
    prefs = await _get_or_create_preferences(session, user)
    return _prefs_out(prefs)


@router.put("/me", response_model=PreferencesOut)
async def update_my_preferences(
    payload: PreferencesPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PreferencesOut:
    prefs = await _get_or_create_preferences(session, user)
    channels = filter_channels_for_user(user, payload.notification_channels)
    if not channels:
        channels = ["email"]
    if not is_pro(user) and set(channels) - {"email"}:
        raise HTTPException(
            status_code=402,
            detail="Multi-channel alerts require Pro. Upgrade at /pricing.",
        )

    if payload.timezone:
        try:
            payload.timezone = validate_iana_timezone(payload.timezone)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err))

    skills = [s.strip() for s in payload.skills if s and s.strip()][:40]
    extra_keywords = [k.strip() for k in payload.keywords if k and k.strip()][:40]
    # Keep keywords filled for older clients / digests that only read keywords.
    prefs.skills = skills
    prefs.keywords = extra_keywords or list(skills)
    prefs.exclude_keywords = payload.exclude_keywords
    prefs.experience_level = _normalize_experience(payload.experience_level)
    prefs.min_budget = payload.min_budget
    prefs.max_budget = payload.max_budget
    prefs.min_hourly_rate = payload.min_hourly_rate
    prefs.sources = payload.sources
    prefs.match_threshold = payload.match_threshold
    prefs.notification_channels = channels
    prefs.digest_mode = payload.digest_mode
    prefs.freelance_focus = payload.freelance_focus
    prefs.hide_agency_leads = payload.hide_agency_leads
    prefs.location = payload.location
    prefs.timezone = payload.timezone
    prefs.digest_days = payload.digest_days
    prefs.digest_time_local = payload.digest_time_local
    prefs.max_per_digest = clamp_digest_limit(user, payload.max_per_digest)
    prefs.notes = payload.notes
    prefs.alert_email = str(payload.alert_email) if payload.alert_email else user.email
    prefs.slack_webhook_url = payload.slack_webhook_url
    prefs.telegram_chat_id = payload.telegram_chat_id
    prefs.discord_webhook_url = payload.discord_webhook_url
    prefs.whatsapp_to = payload.whatsapp_to
    prefs.custom_webhook_url = payload.custom_webhook_url
    prefs.cadence = payload.cadence
    prefs.quiet_hours_enabled = payload.quiet_hours_enabled
    prefs.quiet_hours_start = payload.quiet_hours_start
    prefs.quiet_hours_end = payload.quiet_hours_end
    prefs.event_types = payload.event_types
    prefs.is_paused = payload.is_paused
    prefs.is_unsubscribed = payload.is_unsubscribed
    prefs.empty_digest_policy = payload.empty_digest_policy
    prefs.immediate_alerts_enabled = payload.immediate_alerts_enabled
    prefs.immediate_alert_threshold = payload.immediate_alert_threshold
    prefs.immediate_alert_cap_per_day = payload.immediate_alert_cap_per_day
    session.add(prefs)
    await session.commit()
    await session.refresh(prefs)
    get_recommendation_cache().invalidate_user(str(user.id))
    return _prefs_out(prefs)


@router.post("/pause", response_model=PreferencesOut)
async def pause_notifications(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PreferencesOut:
    """Pauses digest and alert deliveries without losing configured criteria."""
    prefs = await _get_or_create_preferences(session, user)
    prefs.is_paused = True
    session.add(prefs)
    await session.commit()
    await session.refresh(prefs)
    return _prefs_out(prefs)


@router.post("/resume", response_model=PreferencesOut)
async def resume_notifications(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PreferencesOut:
    """Resumes paused digest and alert deliveries."""
    prefs = await _get_or_create_preferences(session, user)
    prefs.is_paused = False
    session.add(prefs)
    await session.commit()
    await session.refresh(prefs)
    return _prefs_out(prefs)


@router.post("/unsubscribe", response_model=PreferencesOut)
async def unsubscribe_notifications(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PreferencesOut:
    """One-click authenticated unsubscribe from all outbound email digests and alerts."""
    from datetime import UTC, datetime

    prefs = await _get_or_create_preferences(session, user)
    prefs.is_unsubscribed = True
    prefs.unsubscribed_at = datetime.now(UTC)
    session.add(prefs)
    await session.commit()
    await session.refresh(prefs)
    return _prefs_out(prefs)


async def _load_match_candidate_jobs(
    session: AsyncSession,
    prefs: UserPreferences,
    *,
    limit: int = 300,
    offset: int = 0,
) -> list[JobRecord]:
    repo = SQLAlchemyJobRepository(session)
    return await repo.list_match_candidates(
        skills=list(getattr(prefs, "skills", None) or []),
        keywords=list(prefs.keywords or []),
        exclude_keywords=list(prefs.exclude_keywords or []),
        sources=list(prefs.sources or []),
        min_budget=prefs.min_budget,
        max_budget=prefs.max_budget,
        min_hourly_rate=getattr(prefs, "min_hourly_rate", None),
        limit=limit,
        offset=offset,
    )


@router.get("/matches")
async def list_matches(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> dict:
    prefs = await _get_or_create_preferences(session, user)
    skipped, _ = await _lead_status_sets(session, user.id)
    feedback = MatchFeedbackService(session)
    learning_enabled = await feedback.has_ranking_consent(user.id)
    pipeline = RankingPipeline()
    meta = pipeline.recommendation_meta(prefs, learning_enabled=learning_enabled)
    prefs_updated = getattr(prefs, "updated_at", None)
    cache_key = recommendation_cache_key(
        user_id=str(user.id),
        prefs_updated_at=prefs_updated.isoformat() if prefs_updated else None,
        score_version=str(meta["score_version"]),
        retrieval_mode=str(meta["retrieval_mode"]),
        limit=limit,
        offset=offset,
        freelance_focus=bool(getattr(prefs, "freelance_focus", True)),
    )
    cache = get_recommendation_cache()
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return {**cached, "cache_hit": True}

    repo = SQLAlchemyJobRepository(session)
    raw_jobs = await _load_match_candidate_jobs(
        session, prefs, limit=max(300, limit + offset)
    )
    jobs = [
        j
        for j in raw_jobs
        if not getattr(j, "is_expired", False) and j.id not in skipped
    ]
    skill_weights = await feedback.skill_weights(user.id)
    findings_service = LeadFindingsService(pipeline=pipeline)
    freelance_focus = bool(getattr(prefs, "freelance_focus", True))
    ranked = pipeline.rank(
        jobs,
        prefs,
        skill_weights=skill_weights,
        learning_enabled=learning_enabled,
    )[offset : offset + limit]
    ineligible = pipeline.sample_ineligible(jobs[:80], prefs, limit=5)
    items = []
    for item in ranked:
        match = item.as_job_match()
        finding = findings_service._from_match(
            match, freelance_focus=freelance_focus, ranked=item
        )
        job_data = await repo.to_candidate_dict(match.job)
        items.append(
            {
                **job_data,
                "match_score": finding.score,
                "fit_score": finding.fit_score,
                "score_version": finding.score_version,
                "explanation": finding.explanation,
                "why_shown": finding.why_shown,
                "eligibility": (finding.explanation or {}).get("eligibility"),
                "freelance_fit": finding.freelance_fit,
                "matched_keywords": match.matched_keywords,
                "match_reasons": match.reasons,
                "freshness_score": match.freshness_score,
                "client_quality_score": match.client_quality_score,
                "red_flags": match.red_flags or [],
            }
        )
    payload = {
        "total": len(items),
        "items": items,
        "score_version": meta["score_version"],
        "retrieval_mode": meta["retrieval_mode"],
        "candidate_stage": "sql_ilike",
        "learning_enabled": learning_enabled,
        "subscription_affects_organic_rank": False,
        "ineligible_samples": ineligible,
        "offset": offset,
        "limit": limit,
        "cache_hit": False,
    }
    cache.set(cache_key, payload, user_id=str(user.id))
    return payload


@router.get("/findings")
async def list_findings(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 10,
    freelance_focus: bool | None = None,
    include_skipped: bool = False,
) -> dict:
    """Decision digest: why a lead matters now and what to do next."""
    prefs = await _get_or_create_preferences(session, user)
    focus = (
        bool(freelance_focus)
        if freelance_focus is not None
        else bool(getattr(prefs, "freelance_focus", True))
    )
    # Do not auto-archive on findings GET — it raced Save/Undo and wiped counts.
    actions_res = await session.execute(
        select(UserLeadAction).where(
            UserLeadAction.user_id == user.id,
            UserLeadAction.deleted_at.is_(None),
        )
    )
    lead_actions = {row.job_id: row.status for row in actions_res.scalars().all()}

    apps_res = await session.execute(
        select(JobApplication)
        .where(JobApplication.user_id == user.id)
        .order_by(JobApplication.created_at.desc())
    )
    applications: dict[int, dict[str, Any]] = {}
    for app in apps_res.scalars().all():
        if app.job_id not in applications:
            applications[app.job_id] = {
                "id": app.id,
                "proposal": app.proposal,
                "bid_amount": app.bid_amount,
                "currency": app.currency,
                "delivery_days": app.delivery_days,
                "milestone_plan": app.milestone_plan,
                "status": app.status,
                "created_at": app.created_at.isoformat() if app.created_at else None,
            }

    feedback = MatchFeedbackService(session)
    learning_enabled = await feedback.has_ranking_consent(user.id)
    pipeline = RankingPipeline()
    meta = pipeline.recommendation_meta(prefs, learning_enabled=learning_enabled)
    prefs_updated = getattr(prefs, "updated_at", None)
    cache_key = recommendation_cache_key(
        user_id=str(user.id),
        prefs_updated_at=prefs_updated.isoformat() if prefs_updated else None,
        score_version=str(meta["score_version"]),
        retrieval_mode=str(meta["retrieval_mode"]),
        limit=limit,
        freelance_focus=focus,
        include_skipped=include_skipped,
    )
    actioned_ids = [
        jid
        for jid, status in lead_actions.items()
        if status in {"save", "pitched", "won"}
        or (include_skipped and status == "skip")
    ]
    preserved = set(actioned_ids)

    repo = SQLAlchemyJobRepository(session)
    jobs = await _load_match_candidate_jobs(session, prefs, limit=300)
    # Always include actioned leads so Saved/Pitched stay visible even when the
    # source is later filtered as noise or falls outside the candidate window.
    if actioned_ids:
        known = {j.id for j in jobs if j.id is not None}
        missing = [jid for jid in actioned_ids if jid not in known]
        if missing:
            extra_res = await session.execute(
                select(JobRecord).where(JobRecord.id.in_(missing))
            )
            jobs = list(jobs) + list(extra_res.scalars().all())
    # Purge listicles/directories already stored (e.g. starterindex) before cache.
    purge_candidates = [
        j for j in jobs if j.id is None or j.id not in preserved
    ]
    await _purge_non_opportunity_jobs(session, purge_candidates, persist=True)
    jobs = [
        j
        for j in jobs
        if not getattr(j, "is_expired", False) or (j.id is not None and j.id in preserved)
    ]

    cache = get_recommendation_cache()
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return {**cached, "cache_hit": True}

    total_indexed = await repo.count_jobs()
    skill_weights = await feedback.skill_weights(user.id)
    payload = LeadFindingsService(pipeline=pipeline).build(
        jobs,
        prefs,
        limit=limit,
        freelance_focus=focus,
        lead_actions=lead_actions,
        applications=applications,
        include_skipped=include_skipped,
        skill_weights=skill_weights,
        learning_enabled=learning_enabled,
        total_indexed=total_indexed,
    )
    payload["score_version"] = meta["score_version"]
    payload["retrieval_mode"] = meta["retrieval_mode"]
    payload["candidate_stage"] = "sql_ilike"
    payload["learning_enabled"] = learning_enabled
    payload["subscription_affects_organic_rank"] = False
    payload["ineligible_samples"] = pipeline.sample_ineligible(jobs[:80], prefs, limit=5)
    payload["cache_hit"] = False
    cache.set(cache_key, payload, user_id=str(user.id))
    return payload


@router.put("/leads/{job_id}/action")
async def set_lead_action(
    job_id: int,
    payload: LeadActionPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Persist Save / Skip for a lead, or clear the stored action."""
    from backend.application.services.pipeline import PipelineService, stage_for_status

    job = await session.get(JobRecord, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    pipeline = PipelineService(session)

    if payload.status == "clear":
        # Soft-delete only — keep client_write_version so a late original write
        # cannot recreate the row after Undo.
        await pipeline.clear_lead(
            user_id=user.id,
            job_id=job_id,
            write_version=payload.write_version,
        )
        await session.commit()
        get_recommendation_cache().invalidate_user(str(user.id))
        return {"job_id": job_id, "status": None}

    if payload.reason_only:
        # Attach Why? reason without undeleting a cleared lead (Unsave race).
        row = await pipeline.patch_reason(
            user_id=user.id,
            job_id=job_id,
            status=payload.status,
            reason=payload.reason,
            write_version=payload.write_version,
        )
        await session.commit()
        get_recommendation_cache().invalidate_user(str(user.id))
        if row is None or getattr(row, "deleted_at", None) is not None:
            return {"job_id": job_id, "status": None, "reason": None}
        return {
            "job_id": job_id,
            "status": row.status,
            "reason": getattr(row, "reason", None),
            "feedback_kind": getattr(row, "feedback_kind", None),
        }

    row = await pipeline.sync_from_legacy_status(
        user_id=user.id,
        job_id=job_id,
        status=payload.status,
        reason=payload.reason,
        feedback_kind=payload.feedback_kind or payload.status,
        write_version=payload.write_version,
    )
    await session.commit()
    if row is not None:
        await session.refresh(row)
    get_recommendation_cache().invalidate_user(str(user.id))
    return {
        "job_id": job_id,
        "status": row.status if row else payload.status,
        "pipeline_stage": (
            getattr(row, "pipeline_stage", None)
            if row
            else stage_for_status(payload.status)
        ),
        "reason": getattr(row, "reason", None) if row else payload.reason,
        "feedback_kind": getattr(row, "feedback_kind", None) if row else payload.feedback_kind,
    }


def _estimate_job_value(
    job: JobRecord | None, bid_amount: float | None
) -> float:
    if bid_amount is not None and bid_amount > 0:
        return float(bid_amount)
    if job is None:
        return 0.0
    b_min = float(job.budget_min) if job.budget_min and job.budget_min > 0 else 0.0
    b_max = float(job.budget_max) if job.budget_max and job.budget_max > 0 else 0.0
    if b_min > 0 and b_max > 0:
        return round((b_min + b_max) / 2.0, 2)
    return b_max or b_min


@router.get("/pipeline-stats")
async def get_pipeline_stats(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Compute lead conversion funnel metrics and estimated pipeline value in O(N).

    Do not auto-archive on this GET — mutating saves/pitches here raced optimistic
    UI and made counts snap back a few seconds after Save/Undo.
    """
    actions_res = await session.execute(
        select(UserLeadAction, JobRecord)
        .outerjoin(JobRecord, UserLeadAction.job_id == JobRecord.id)
        .where(
            UserLeadAction.user_id == user.id,
            UserLeadAction.deleted_at.is_(None),
        )
    )
    apps_res = await session.execute(
        select(JobApplication)
        .where(JobApplication.user_id == user.id)
        .order_by(JobApplication.created_at.desc())
    )
    bid_by_job: dict[int, float] = {}
    for app in apps_res.scalars().all():
        if app.job_id not in bid_by_job and app.bid_amount is not None:
            bid_by_job[app.job_id] = float(app.bid_amount)

    saved_count = 0
    pitched_count = 0
    won_count = 0
    skipped_count = 0
    saved_value = 0.0
    pitched_value = 0.0
    won_value = 0.0

    for action, job in actions_res.all():
        est = _estimate_job_value(job, bid_by_job.get(action.job_id))
        if action.status == "save":
            saved_count += 1
            saved_value += est
        elif action.status == "pitched":
            pitched_count += 1
            pitched_value += est
        elif action.status == "won":
            won_count += 1
            won_value += est
        elif action.status == "skip":
            skipped_count += 1

    total_engaged = saved_count + pitched_count + won_count
    total_pitched = pitched_count + won_count
    pitch_rate = round(total_pitched / total_engaged, 3) if total_engaged > 0 else 0.0
    win_rate = round(won_count / total_pitched, 3) if total_pitched > 0 else 0.0

    return {
        "saved_count": saved_count,
        "pitched_count": pitched_count,
        "won_count": won_count,
        "skipped_count": skipped_count,
        "total_engaged": total_engaged,
        "pitch_rate": pitch_rate,
        "win_rate": win_rate,
        "saved_value": round(saved_value, 2),
        "pitched_value": round(pitched_value, 2),
        "won_value": round(won_value, 2),
        "active_pipeline_value": round(saved_value + pitched_value, 2),
    }


@router.get("/demo-findings")
async def demo_findings(
    session: Annotated[AsyncSession, Depends(get_db)],
    keywords: str = "python,react,fastapi,typescript,remote",
    limit: int = 10,
    freelance_focus: bool = True,
) -> dict:
    """Unauthenticated lead findings digest for the desk demo."""
    repo = SQLAlchemyJobRepository(session)
    jobs = await repo.list_recent(limit=300)
    # Filter noise in-memory only — demo traffic must not expire inventory.
    jobs = await _purge_non_opportunity_jobs(session, list(jobs), persist=False)
    total_indexed = await repo.count_jobs()
    prefs = UserPreferences(
        user_id="demo",
        keywords=[part.strip() for part in keywords.split(",") if part.strip()],
        exclude_keywords=[],
        sources=[],
        notification_channels=[],
        match_threshold=0.2,
    )
    # Empty inventory is a normal state — return an empty digest, not a 404.
    return LeadFindingsService().build(
        jobs, prefs, limit=limit, freelance_focus=freelance_focus, total_indexed=total_indexed
    )


@router.get("/demo-matches")
async def demo_matches(
    session: Annotated[AsyncSession, Depends(get_db)],
    keywords: str = "python,react,fastapi,typescript,remote",
    limit: int = 50,
) -> dict:
    """Unauthenticated matching for the demo dashboard."""
    repo = SQLAlchemyJobRepository(session)
    jobs = await repo.list_recent(limit=300)
    total_indexed = await repo.count_jobs()
    prefs = UserPreferences(
        user_id="demo",
        keywords=[part.strip() for part in keywords.split(",") if part.strip()],
        exclude_keywords=[],
        sources=[],
        notification_channels=[],
        match_threshold=0.2,
    )
    matcher = MatchingService()
    findings_service = LeadFindingsService(matcher)
    matches = matcher.rank_jobs(jobs, prefs)[:limit]
    items = []
    for match in matches:
        finding = findings_service._from_match(match, freelance_focus=True)
        job_data = await repo.to_candidate_dict(match.job)
        items.append(
            {
                **job_data,
                "match_score": finding.score,
                "matched_keywords": match.matched_keywords,
                "match_reasons": match.reasons,
                "freshness_score": match.freshness_score,
                "client_quality_score": match.client_quality_score,
                "red_flags": match.red_flags or [],
            }
        )
    return {"total": len(items), "keywords": prefs.keywords, "items": items}


class TestWebhookPayload(BaseModel):
    webhook_url: str | None = Field(default=None, max_length=1024)


@router.get("/learned-affinities")
async def get_my_learned_affinities(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    """Inspect learned skill affinities derived automatically from Save/Skip history."""
    return await MatchFeedbackService(session).get_affinity_profile(user.id)


@router.post("/learned-affinities/reset")
async def reset_my_learned_affinities(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    """Reset learned Save/Skip affinities. Hunt Rules are unchanged."""
    result = await MatchFeedbackService(session).reset_learned_affinities(user.id)
    get_recommendation_cache().invalidate_user(str(user.id))
    return result


@router.get("/match-profile")
async def get_match_profile(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    """Inspect the typed match profile derived from Hunt Rules (+ consented learning)."""
    prefs = await _get_or_create_preferences(session, user)
    feedback = MatchFeedbackService(session)
    learning_enabled = await feedback.has_ranking_consent(user.id)
    skill_weights = await feedback.skill_weights(user.id)
    profile = RankingPipeline().build_profile(
        prefs,
        skill_weights=skill_weights,
        learning_enabled=learning_enabled,
    )
    return profile.to_dict()


@router.get("/recommendation-meta")
async def get_recommendation_meta(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 10,
    offset: int = 0,
) -> dict[str, object]:
    """Ranking version, retrieval mode, and stable cache key inputs."""
    prefs = await _get_or_create_preferences(session, user)
    feedback = MatchFeedbackService(session)
    learning_enabled = await feedback.has_ranking_consent(user.id)
    pipeline = RankingPipeline()
    meta = pipeline.recommendation_meta(prefs, learning_enabled=learning_enabled)
    prefs_updated = getattr(prefs, "updated_at", None)
    cache_key = recommendation_cache_key(
        user_id=str(user.id),
        prefs_updated_at=prefs_updated.isoformat() if prefs_updated else None,
        score_version=str(meta["score_version"]),
        retrieval_mode=str(meta["retrieval_mode"]),
        limit=limit,
        offset=offset,
        freelance_focus=bool(getattr(prefs, "freelance_focus", True)),
    )
    return {
        **meta,
        "consent_purpose": RANKING_CONSENT_PURPOSE,
        "cache_key": cache_key,
        "limit": limit,
        "offset": offset,
    }


@router.post("/match-feedback")
async def post_match_feedback(
    payload: MatchFeedbackPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    """Structured ranking feedback. Apply-click is recorded but not treated as success."""
    job = await session.get(JobRecord, payload.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await session.execute(
        select(UserLeadAction).where(
            UserLeadAction.user_id == user.id,
            UserLeadAction.job_id == payload.job_id,
        )
    )
    row = result.scalar_one_or_none()

    if payload.kind == "clear":
        from backend.application.services.pipeline import PipelineService

        await PipelineService(session).clear_lead(
            user_id=user.id,
            job_id=payload.job_id,
            write_version=payload.write_version,
        )
        await session.commit()
        get_recommendation_cache().invalidate_user(str(user.id))
        return {"job_id": payload.job_id, "status": None, "feedback_kind": "clear"}

    if payload.kind == "apply_click":
        # Weak interest only — never invent a Save row (clicks are not success).
        # Distinguish apply-click from confirmed application (Phase 08).
        if row is not None:
            row.feedback_kind = "apply_click"
            if payload.reason:
                row.reason = payload.reason
            if getattr(row, "apply_clicked_at", None) is None:
                from datetime import datetime, timezone

                row.apply_clicked_at = datetime.now(timezone.utc)
            session.add(row)
            await session.commit()
            status_out = row.status
        else:
            # Record click timestamp only if a lead already exists — do not invent Save.
            status_out = None
        return {
            "job_id": payload.job_id,
            "status": status_out,
            "feedback_kind": "apply_click",
            "counts_as_success": False,
            "applied_confirmed": False,
        }

    prefs = await _get_or_create_preferences(session, user)

    if payload.kind == "hide_source":
        status = "skip"
        reason = payload.reason or f"hide_source:{job.source_name}"
        kind = "hide_source"
        # Persist source exclusion into Hunt Rules so future SQL retrieval drops it.
        source_token = (job.source_name or "").strip().lower()
        if source_token and len(source_token) >= 3:
            excludes = [
                str(x).strip().lower()
                for x in (prefs.exclude_keywords or [])
                if x and str(x).strip()
            ]
            if source_token not in excludes:
                excludes.append(source_token)
                prefs.exclude_keywords = excludes[:40]
                session.add(prefs)
    elif payload.kind == "outcome":
        if payload.outcome == "contract":
            status = "won"
        elif payload.outcome == "interview":
            status = "pitched"
        elif payload.outcome == "rejected":
            status = "skip"
        else:
            status = "pitched"
        reason = payload.reason or (payload.outcome or "outcome")
        kind = "outcome"
    elif payload.kind == "save":
        status = "save"
        reason = payload.reason
        kind = "save"
    else:
        status = "skip"
        reason = payload.reason
        kind = "skip"

    from backend.application.services.pipeline import PipelineService

    row = await PipelineService(session).sync_from_legacy_status(
        user_id=user.id,
        job_id=payload.job_id,
        status=status,
        reason=reason,
        feedback_kind=kind,
        write_version=payload.write_version,
    )
    await session.commit()
    if row is not None:
        await session.refresh(row)
    get_recommendation_cache().invalidate_user(str(user.id))
    return {
        "job_id": payload.job_id,
        "status": row.status if row else status,
        "pipeline_stage": getattr(row, "pipeline_stage", None) if row else None,
        "reason": row.reason if row else reason,
        "feedback_kind": row.feedback_kind if row else kind,
        "counts_as_success": kind in {"save", "outcome"}
        and status in {"save", "pitched", "won"},
    }


@router.post("/embeddings/reindex")
async def reindex_job_embeddings(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 200,
    force: bool = False,
    async_job: bool = True,
) -> dict[str, object]:
    """Safe embedding reindex with budget limits. Falls back to sync if workers offline."""
    limit = max(1, min(int(limit), 500))
    if async_job:
        try:
            from workers.availability import celery_workers_online
            from workers.jobs.tasks import reindex_embeddings_task

            if celery_workers_online():
                result = reindex_embeddings_task.delay(limit=limit, force=force)
                return {
                    "queued": True,
                    "task_id": result.id,
                    "limit": limit,
                    "force": force,
                    "model_version": EmbeddingIndex().model_version,
                }
        except Exception:  # noqa: BLE001 — sync fallback
            pass

    repo = SQLAlchemyJobRepository(session)
    jobs = await repo.list_recent(limit=limit)
    index = EmbeddingIndex()
    await index.persist_dirty(
        session, jobs, batch_limit=min(64, limit), budget_ms=2000, force=force
    )
    return {
        "queued": False,
        "sync": True,
        **index.metrics_dict(),
    }


@router.post("/test-webhook")
async def test_user_webhook(
    payload: TestWebhookPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    """Send a test verification ping to the custom webhook URL."""
    url = (payload.webhook_url or "").strip()
    if not url:
        prefs = await _get_or_create_preferences(session, user)
        url = (getattr(prefs, "custom_webhook_url", None) or "").strip()
    if not url:
        raise HTTPException(
            status_code=400,
            detail="No webhook URL provided or configured in preferences.",
        )
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(
            status_code=400,
            detail="Webhook URL must begin with http:// or https://",
        )

    parsed = urllib.parse.urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if hostname in {"169.254.169.254", "metadata.google.internal"}:
        raise HTTPException(
            status_code=400,
            detail="Forbidden destination host.",
        )

    test_envelope = NotificationEnvelope(
        id=f"test-{random.randint(1, 100000)}",
        user_id=user.id,
        title="⚡ Freelance Automation Webhook Test",
        body="Verification ping from your Freelance Automation lead engine. Integration successful!",
        channels=[NotificationChannel.WEBHOOK],
        priority=NotificationPriority.NORMAL,
        digest=False,
        ai_summary="Webhook verification ping",
        actions=[],
        destinations={"custom_webhook_url": url},
        metadata={"event_type": "test_ping", "user_email": user.email},
    )

    adapter = CustomWebhookAdapter(endpoint=url)
    result = await adapter.send(test_envelope)
    if result.delivered:
        return {
            "success": True,
            "message": "Webhook test delivered successfully.",
            "status_code": result.message_id,
        }
    return {
        "success": False,
        "error": result.error or "Failed to deliver webhook payload.",
    }
