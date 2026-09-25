from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from database.core.session import get_db
from database.models.preference import UserPreferences
from database.models.user import User
from backend.infrastructure.repositories.job_repository import SQLAlchemyJobRepository
from backend.application.services.billing import filter_channels_for_user, is_pro
from backend.application.services.lead_findings import LeadFindingsService
from backend.application.services.matching import MatchingService

router = APIRouter(prefix="/preferences", tags=["preferences"])


class PreferencesPayload(BaseModel):
    keywords: list[str] = Field(default_factory=lambda: ["python", "fastapi", "react"], max_length=40)
    exclude_keywords: list[str] = Field(default_factory=list, max_length=40)
    min_budget: float | None = None
    max_budget: float | None = None
    sources: list[str] = Field(default_factory=list, max_length=20)
    match_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    notification_channels: list[str] = Field(default_factory=lambda: ["email"], max_length=10)
    digest_mode: bool = False
    notes: str | None = Field(default=None, max_length=2000)
    alert_email: EmailStr | None = None
    slack_webhook_url: str | None = Field(default=None, max_length=1024)
    telegram_chat_id: str | None = Field(default=None, max_length=128)
    discord_webhook_url: str | None = Field(default=None, max_length=1024)
    whatsapp_to: str | None = Field(default=None, max_length=64)


class PreferencesOut(PreferencesPayload):
    id: int
    user_id: str


def _prefs_out(prefs: UserPreferences) -> PreferencesOut:
    return PreferencesOut(
        id=prefs.id,
        user_id=prefs.user_id,
        keywords=prefs.keywords or [],
        exclude_keywords=prefs.exclude_keywords or [],
        min_budget=prefs.min_budget,
        max_budget=prefs.max_budget,
        sources=prefs.sources or [],
        match_threshold=prefs.match_threshold,
        notification_channels=prefs.notification_channels or [],
        digest_mode=bool(prefs.digest_mode),
        notes=prefs.notes,
        alert_email=prefs.alert_email,
        slack_webhook_url=prefs.slack_webhook_url,
        telegram_chat_id=prefs.telegram_chat_id,
        discord_webhook_url=prefs.discord_webhook_url,
        whatsapp_to=prefs.whatsapp_to,
    )


async def _get_or_create_preferences(session: AsyncSession, user: User) -> UserPreferences:
    result = await session.execute(select(UserPreferences).where(UserPreferences.user_id == user.id))
    prefs = result.scalar_one_or_none()
    if prefs:
        return prefs
    prefs = UserPreferences(
        user_id=user.id,
        keywords=["python", "fastapi", "react", "typescript"],
        exclude_keywords=[],
        sources=[],
        notification_channels=["email"],
        match_threshold=0.35,
        digest_mode=False,
        alert_email=user.email,
    )
    session.add(prefs)
    await session.commit()
    await session.refresh(prefs)
    return prefs


@router.get("/me", response_model=PreferencesOut)
async def get_my_preferences(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PreferencesOut:
    prefs = await _get_or_create_preferences(session, user)
    return _prefs_out(prefs)


@router.put("/me", response_model=PreferencesOut)
async def update_my_preferences(
    payload: PreferencesPayload,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PreferencesOut:
    prefs = await _get_or_create_preferences(session, user)
    channels = filter_channels_for_user(user, payload.notification_channels)
    if not channels:
        channels = ["email"]
    if not is_pro(user) and set(channels) - {"email"}:
        raise HTTPException(status_code=402, detail="Multi-channel alerts require Pro. Upgrade at /pricing.")

    prefs.keywords = payload.keywords
    prefs.exclude_keywords = payload.exclude_keywords
    prefs.min_budget = payload.min_budget
    prefs.max_budget = payload.max_budget
    prefs.sources = payload.sources
    prefs.match_threshold = payload.match_threshold
    prefs.notification_channels = channels
    prefs.digest_mode = payload.digest_mode
    prefs.notes = payload.notes
    prefs.alert_email = str(payload.alert_email) if payload.alert_email else user.email
    prefs.slack_webhook_url = payload.slack_webhook_url
    prefs.telegram_chat_id = payload.telegram_chat_id
    prefs.discord_webhook_url = payload.discord_webhook_url
    prefs.whatsapp_to = payload.whatsapp_to
    session.add(prefs)
    await session.commit()
    await session.refresh(prefs)
    return _prefs_out(prefs)


@router.get("/matches")
async def list_matches(
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    prefs = await _get_or_create_preferences(session, user)
    repo = SQLAlchemyJobRepository(session)
    jobs = await repo.list_recent(limit=300)
    matcher = MatchingService()
    matches = matcher.rank_jobs(jobs, prefs)[:limit]
    items = []
    for match in matches:
        job_data = await repo.to_candidate_dict(match.job)
        items.append(
            {
                **job_data,
                "match_score": match.score,
                "matched_keywords": match.matched_keywords,
                "match_reasons": match.reasons,
                "freshness_score": match.freshness_score,
                "client_quality_score": match.client_quality_score,
                "red_flags": match.red_flags or [],
            }
        )
    return {"total": len(items), "items": items}


@router.get("/findings")
async def list_findings(
    limit: int = 10,
    freelance_focus: bool = True,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Decision digest: why a lead matters now and what to do next."""
    prefs = await _get_or_create_preferences(session, user)
    repo = SQLAlchemyJobRepository(session)
    jobs = await repo.list_recent(limit=300)
    return LeadFindingsService().build(
        jobs, prefs, limit=limit, freelance_focus=freelance_focus
    )


@router.get("/demo-findings")
async def demo_findings(
    keywords: str = "python,react,fastapi,typescript,remote",
    limit: int = 10,
    freelance_focus: bool = True,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Unauthenticated lead findings digest for the desk demo."""
    repo = SQLAlchemyJobRepository(session)
    jobs = await repo.list_recent(limit=300)
    prefs = UserPreferences(
        user_id="demo",
        keywords=[part.strip() for part in keywords.split(",") if part.strip()],
        exclude_keywords=[],
        sources=[],
        notification_channels=[],
        match_threshold=0.2,
    )
    payload = LeadFindingsService().build(
        jobs, prefs, limit=limit, freelance_focus=freelance_focus
    )
    if not payload["items"] and not jobs:
        raise HTTPException(
            status_code=404,
            detail="No jobs in the database yet. Call POST /jobs/scrape first.",
        )
    return payload


@router.get("/demo-matches")
async def demo_matches(
    keywords: str = "python,react,fastapi,typescript,remote",
    limit: int = 50,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Unauthenticated matching for the demo dashboard."""
    repo = SQLAlchemyJobRepository(session)
    jobs = await repo.list_recent(limit=300)
    prefs = UserPreferences(
        user_id="demo",
        keywords=[part.strip() for part in keywords.split(",") if part.strip()],
        exclude_keywords=[],
        sources=[],
        notification_channels=[],
        match_threshold=0.2,
    )
    matcher = MatchingService()
    matches = matcher.rank_jobs(jobs, prefs)[:limit]
    items = []
    for match in matches:
        job_data = await repo.to_candidate_dict(match.job)
        items.append(
            {
                **job_data,
                "match_score": match.score,
                "matched_keywords": match.matched_keywords,
                "match_reasons": match.reasons,
                "freshness_score": match.freshness_score,
                "client_quality_score": match.client_quality_score,
                "red_flags": match.red_flags or [],
            }
        )
    if not items and not jobs:
        raise HTTPException(
            status_code=404,
            detail="No jobs in the database yet. Call POST /jobs/scrape first.",
        )
    return {"total": len(items), "keywords": prefs.keywords, "items": items}
