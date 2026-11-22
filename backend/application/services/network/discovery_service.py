"""Phase 13 — Public opt-in talent directory discovery, non-discriminatory filtering, fair newcomer exposure."""

from __future__ import annotations

from datetime import datetime, timezone
import random
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models.network import (
    PublicListingConsent,
    RatePreference,
    TalentProfile,
    TalentSkill,
    WorkAvailability,
)
from database.models.user import User


class DiscoveryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search_directory(
        self,
        skills: list[str] | None = None,
        work_type: str | None = None,
        min_rate: float | None = None,
        max_rate: float | None = None,
        currency: str | None = None,
        availability_status: str | None = None,
        min_verification_level: int | None = None,
        primary_segment: str | None = None,
        include_sample: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search the talent directory with strict privacy and non-discriminatory filters.

        Private by default:
        - Only profiles with is_published=True, status='active', opt_in_directory=True
        - Exclude profiles with expired availability
        - Real users only unless include_sample=True (demo isolated)
        """
        now = datetime.now(timezone.utc)

        stmt = (
            select(TalentProfile)
            .join(TalentProfile.listing_consent)
            .join(TalentProfile.availability)
            .join(TalentProfile.rate_preference)
            .where(
                TalentProfile.is_published == True,  # Must be published
                TalentProfile.status == "active",  # Must be active
                PublicListingConsent.opt_in_directory == True,  # Explicit opt-in directory consent
                WorkAvailability.expires_at > now,  # Clear availability expiry check
            )
            .options(
                selectinload(TalentProfile.skills),
                selectinload(TalentProfile.artifacts),
                selectinload(TalentProfile.availability),
                selectinload(TalentProfile.rate_preference),
                selectinload(TalentProfile.listing_consent),
                selectinload(TalentProfile.verification_claims),
            )
        )

        if not include_sample:
            stmt = stmt.where(TalentProfile.is_sample == False)

        if primary_segment:
            stmt = stmt.where(TalentProfile.primary_segment == primary_segment)

        if work_type:
            stmt = stmt.where(RatePreference.rate_type == work_type.lower())

        if currency:
            stmt = stmt.where(RatePreference.currency == currency.upper())

        if min_rate is not None:
            stmt = stmt.where(RatePreference.min_rate >= min_rate)

        if max_rate is not None:
            stmt = stmt.where(RatePreference.min_rate <= max_rate)

        if availability_status:
            stmt = stmt.where(WorkAvailability.status == availability_status.lower())

        res = await self.session.execute(stmt)
        all_profiles = res.scalars().all()

        # Skill filtering in Python for flexible matching
        matched: list[TalentProfile] = []
        clean_skills = [s.strip().lower() for s in skills if s.strip()] if skills else []

        for p in all_profiles:
            if clean_skills:
                profile_skills = [s.skill_name.lower() for s in p.skills]
                # Check if at least one requested skill matches
                if not any(req in profile_skills or any(req in ps for ps in profile_skills) for req in clean_skills):
                    continue

            if min_verification_level:
                verified_levels = [
                    c.level for c in p.verification_claims if c.status == "verified"
                ]
                if not verified_levels or max(verified_levels) < min_verification_level:
                    continue

            matched.append(p)

        total_count = len(matched)

        # Fair newcomer exposure:
        # Separate established from newcomers and interleave or ensure newcomers are fairly ranked
        newcomers: list[TalentProfile] = []
        established: list[TalentProfile] = []

        for p in matched:
            # If profile has < 2 verified claims, consider newcomer
            verified_count = sum(1 for c in p.verification_claims if c.status == "verified")
            if verified_count <= 1:
                newcomers.append(p)
            else:
                established.append(p)

        # Interleave so newcomers get equal exposure on discovery page
        combined: list[TalentProfile] = []
        i, j = 0, 0
        while i < len(established) or j < len(newcomers):
            if i < len(established):
                combined.append(established[i])
                i += 1
            if j < len(newcomers):
                combined.append(newcomers[j])
                j += 1

        paged_profiles = combined[offset : offset + limit]

        items = []
        for p in paged_profiles:
            avail = p.availability
            rates = p.rate_preference
            consent = p.listing_consent

            verified_levels = [
                c.level for c in p.verification_claims if c.status == "verified"
            ]
            max_verified_level = max(verified_levels) if verified_levels else 0

            items.append({
                "id": p.id,
                "headline": p.headline,
                "bio": p.bio[:300] if p.bio else None,
                "primary_segment": p.primary_segment,
                "years_experience": p.years_experience,
                "location_display": p.location_display,
                "is_sample": p.is_sample,
                "contact_allowed": bool(consent and consent.allow_platform_contact),
                "search_indexing_consent": bool(consent and consent.search_indexing_consent),
                "verification_level": max_verified_level,
                "is_newcomer": (len(verified_levels) <= 1),
                "availability": {
                    "status": avail.status if avail else "unknown",
                    "hours_per_week": avail.hours_per_week if avail else 0,
                    "expires_at": avail.expires_at.isoformat() if avail and avail.expires_at else None,
                } if avail else None,
                "rates": {
                    "min_rate": rates.min_rate if rates else 0.0,
                    "max_rate": rates.max_rate if rates else None,
                    "currency": rates.currency if rates else "USD",
                    "rate_type": rates.rate_type if rates else "hourly",
                } if rates else None,
                "top_skills": [
                    {"name": s.skill_name, "verified": s.verification_status == "verified"}
                    for s in p.skills[:6]
                ],
                "verified_artifacts_count": sum(
                    1 for a in p.artifacts if a.verification_status == "verified"
                ),
            })

        return {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "items": items,
            "has_more": (offset + limit) < total_count,
        }
