"""Phase 13 — Freelancer profile, skill, portfolio, availability, rates, and privacy consent service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models.network import (
    PortfolioArtifact,
    PublicListingConsent,
    RatePreference,
    TalentProfile,
    TalentSkill,
    WorkAvailability,
)
from database.models.user import User

DEFAULT_INITIAL_SEGMENT = "ai_software_automation"
VALID_CONTRIBUTION_ROLES = {"owner", "core_contributor", "contributor", "lead_architect"}
VALID_AVAILABILITY_STATUSES = {"available", "partially_available", "busy", "unavailable"}
VALID_RATE_TYPES = {"hourly", "fixed", "retainer"}


class ProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_profile_by_user_id(
        self, user_id: str, auto_create: bool = True
    ) -> TalentProfile | None:
        stmt = (
            select(TalentProfile)
            .where(TalentProfile.user_id == user_id)
            .options(
                selectinload(TalentProfile.skills),
                selectinload(TalentProfile.artifacts),
                selectinload(TalentProfile.availability),
                selectinload(TalentProfile.rate_preference),
                selectinload(TalentProfile.listing_consent),
                selectinload(TalentProfile.verification_claims),
            )
        )
        res = await self.session.execute(stmt)
        profile = res.scalar_one_or_none()

        if profile is None and auto_create:
            profile = await self._create_initial_profile(user_id)
        return profile

    async def _create_initial_profile(self, user_id: str) -> TalentProfile:
        profile_id = str(uuid4())
        now = datetime.now(timezone.utc)
        default_expires = now + timedelta(days=30)

        profile = TalentProfile(
            id=profile_id,
            user_id=user_id,
            headline="AI & Software Specialist",
            bio=None,
            primary_segment=DEFAULT_INITIAL_SEGMENT,
            years_experience=1.0,
            location_display=None,
            is_published=False,  # Private by default
            is_draft=True,
            status="private",
            created_at=now,
            updated_at=now,
        )
        self.session.add(profile)
        await self.session.flush()

        # Add default availability with explicit expiry
        availability = WorkAvailability(
            id=str(uuid4()),
            profile_id=profile_id,
            status="available",
            hours_per_week=40,
            available_from=now,
            expires_at=default_expires,
            last_confirmed_at=now,
            updated_at=now,
        )
        self.session.add(availability)

        # Add default rates
        rate_pref = RatePreference(
            id=str(uuid4()),
            profile_id=profile_id,
            min_rate=50.0,
            max_rate=150.0,
            currency="USD",
            rate_type="hourly",
            updated_at=now,
        )
        self.session.add(rate_pref)

        # Add default privacy consent (Private by default, search indexing consent false)
        consent = PublicListingConsent(
            id=str(uuid4()),
            profile_id=profile_id,
            opt_in_directory=False,
            allow_platform_contact=False,
            search_indexing_consent=False,
            consented_at=None,
            updated_at=now,
        )
        self.session.add(consent)
        await self.session.commit()

        # Re-fetch with all eager loads
        return await self.get_profile_by_user_id(user_id, auto_create=False)  # type: ignore

    async def update_profile_details(
        self,
        user_id: str,
        headline: str | None = None,
        bio: str | None = None,
        primary_segment: str | None = None,
        years_experience: float | None = None,
        location_display: str | None = None,
    ) -> TalentProfile:
        profile = await self.get_profile_by_user_id(user_id)
        if not profile:
            raise ValueError("Profile not found")

        if headline is not None:
            if not headline.strip():
                raise ValueError("Headline cannot be blank")
            profile.headline = headline.strip()[:256]
        if bio is not None:
            profile.bio = bio.strip() if bio else None
        if primary_segment is not None:
            profile.primary_segment = primary_segment.strip()[:64]
        if years_experience is not None:
            if years_experience < 0:
                raise ValueError("Years of experience cannot be negative")
            profile.years_experience = float(years_experience)
        if location_display is not None:
            profile.location_display = location_display.strip()[:128] if location_display else None

        profile.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        return profile

    async def add_or_update_skill(
        self,
        user_id: str,
        skill_name: str,
        category: str = "software",
        years_of_experience: float = 1.0,
        skill_id: str | None = None,
    ) -> TalentSkill:
        profile = await self.get_profile_by_user_id(user_id)
        if not profile:
            raise ValueError("Profile not found")

        skill_clean = skill_name.strip()
        if not skill_clean:
            raise ValueError("Skill name cannot be blank")

        if skill_id:
            stmt = select(TalentSkill).where(
                TalentSkill.id == skill_id,
                TalentSkill.profile_id == profile.id,
            )
            res = await self.session.execute(stmt)
            skill = res.scalar_one_or_none()
            if not skill:
                raise ValueError("Skill not found or access denied")
            skill.skill_name = skill_clean
            skill.category = category.strip()
            skill.years_of_experience = max(0.1, float(years_of_experience))
            skill.updated_at = datetime.now(timezone.utc)
        else:
            skill = TalentSkill(
                id=str(uuid4()),
                profile_id=profile.id,
                skill_name=skill_clean,
                category=category.strip(),
                years_of_experience=max(0.1, float(years_of_experience)),
                verification_status="unverified",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.session.add(skill)

        await self.session.commit()
        return skill

    async def remove_skill(self, user_id: str, skill_id: str) -> bool:
        profile = await self.get_profile_by_user_id(user_id)
        if not profile:
            return False
        stmt = select(TalentSkill).where(
            TalentSkill.id == skill_id,
            TalentSkill.profile_id == profile.id,
        )
        res = await self.session.execute(stmt)
        skill = res.scalar_one_or_none()
        if not skill:
            return False
        await self.session.delete(skill)
        await self.session.commit()
        return True

    async def add_or_update_artifact(
        self,
        user_id: str,
        title: str,
        url: str,
        artifact_type: str = "github_repo",
        contribution_role: str = "contributor",
        description: str | None = None,
        artifact_id: str | None = None,
    ) -> PortfolioArtifact:
        """Add or update a portfolio artifact.

        Do not infer ownership merely from repository link; require explicit contribution role.
        """
        profile = await self.get_profile_by_user_id(user_id)
        if not profile:
            raise ValueError("Profile not found")

        role_clean = contribution_role.strip().lower()
        if role_clean not in VALID_CONTRIBUTION_ROLES:
            raise ValueError(f"Invalid contribution role. Must be one of {VALID_CONTRIBUTION_ROLES}")

        url_clean = url.strip()
        if not url_clean.startswith(("http://", "https://")):
            raise ValueError("Portfolio URL must be a valid http(s) URL")

        if artifact_id:
            stmt = select(PortfolioArtifact).where(
                PortfolioArtifact.id == artifact_id,
                PortfolioArtifact.profile_id == profile.id,
            )
            res = await self.session.execute(stmt)
            artifact = res.scalar_one_or_none()
            if not artifact:
                raise ValueError("Artifact not found or access denied")
            artifact.title = title.strip()[:256]
            artifact.url = url_clean[:512]
            artifact.artifact_type = artifact_type.strip()
            artifact.contribution_role = role_clean
            artifact.description = description.strip() if description else None
            artifact.updated_at = datetime.now(timezone.utc)
        else:
            artifact = PortfolioArtifact(
                id=str(uuid4()),
                profile_id=profile.id,
                title=title.strip()[:256],
                url=url_clean[:512],
                artifact_type=artifact_type.strip(),
                contribution_role=role_clean,
                description=description.strip() if description else None,
                verification_status="unverified",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.session.add(artifact)

        await self.session.commit()
        return artifact

    async def remove_artifact(self, user_id: str, artifact_id: str) -> bool:
        profile = await self.get_profile_by_user_id(user_id)
        if not profile:
            return False
        stmt = select(PortfolioArtifact).where(
            PortfolioArtifact.id == artifact_id,
            PortfolioArtifact.profile_id == profile.id,
        )
        res = await self.session.execute(stmt)
        artifact = res.scalar_one_or_none()
        if not artifact:
            return False
        await self.session.delete(artifact)
        await self.session.commit()
        return True

    async def update_availability(
        self,
        user_id: str,
        status: str,
        hours_per_week: int = 40,
        available_from: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> WorkAvailability:
        profile = await self.get_profile_by_user_id(user_id)
        if not profile:
            raise ValueError("Profile not found")

        status_clean = status.strip().lower()
        if status_clean not in VALID_AVAILABILITY_STATUSES:
            raise ValueError(f"Invalid availability status. Must be one of {VALID_AVAILABILITY_STATUSES}")

        now = datetime.now(timezone.utc)
        # Default expiry: 30 days from now if not given
        if expires_at is None:
            expires_at = now + timedelta(days=30)
        elif expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        availability = profile.availability
        if not availability:
            availability = WorkAvailability(
                id=str(uuid4()),
                profile_id=profile.id,
                status=status_clean,
                hours_per_week=hours_per_week,
                available_from=available_from or now,
                expires_at=expires_at,
                last_confirmed_at=now,
                updated_at=now,
            )
            self.session.add(availability)
        else:
            availability.status = status_clean
            availability.hours_per_week = max(1, min(168, hours_per_week))
            availability.available_from = available_from or availability.available_from
            availability.expires_at = expires_at
            availability.last_confirmed_at = now
            availability.updated_at = now

        await self.session.commit()
        return availability

    async def update_rate_preference(
        self,
        user_id: str,
        min_rate: float,
        max_rate: float | None = None,
        currency: str = "USD",
        rate_type: str = "hourly",
    ) -> RatePreference:
        profile = await self.get_profile_by_user_id(user_id)
        if not profile:
            raise ValueError("Profile not found")

        if min_rate < 0:
            raise ValueError("Minimum rate cannot be negative")
        if max_rate is not None and max_rate < min_rate:
            raise ValueError("Maximum rate cannot be less than minimum rate")

        rate_clean = rate_type.strip().lower()
        if rate_clean not in VALID_RATE_TYPES:
            raise ValueError(f"Invalid rate type. Must be one of {VALID_RATE_TYPES}")

        rate_pref = profile.rate_preference
        now = datetime.now(timezone.utc)
        if not rate_pref:
            rate_pref = RatePreference(
                id=str(uuid4()),
                profile_id=profile.id,
                min_rate=min_rate,
                max_rate=max_rate,
                currency=currency.strip().upper()[:8],
                rate_type=rate_clean,
                updated_at=now,
            )
            self.session.add(rate_pref)
        else:
            rate_pref.min_rate = min_rate
            rate_pref.max_rate = max_rate
            rate_pref.currency = currency.strip().upper()[:8]
            rate_pref.rate_type = rate_clean
            rate_pref.updated_at = now

        await self.session.commit()
        return rate_pref

    async def update_listing_consent(
        self,
        user_id: str,
        opt_in_directory: bool,
        allow_platform_contact: bool = False,
        search_indexing_consent: bool = False,
    ) -> PublicListingConsent:
        profile = await self.get_profile_by_user_id(user_id)
        if not profile:
            raise ValueError("Profile not found")

        consent = profile.listing_consent
        now = datetime.now(timezone.utc)
        if not consent:
            consent = PublicListingConsent(
                id=str(uuid4()),
                profile_id=profile.id,
                opt_in_directory=opt_in_directory,
                allow_platform_contact=allow_platform_contact,
                search_indexing_consent=search_indexing_consent,
                consented_at=now if opt_in_directory else None,
                updated_at=now,
            )
            self.session.add(consent)
        else:
            consent.opt_in_directory = opt_in_directory
            consent.allow_platform_contact = allow_platform_contact
            consent.search_indexing_consent = search_indexing_consent
            if opt_in_directory and not consent.consented_at:
                consent.consented_at = now
            elif not opt_in_directory:
                consent.consented_at = None
            consent.updated_at = now

        # If user opts out of directory, unpublish profile immediately
        if not opt_in_directory and profile.is_published:
            profile.is_published = False
            profile.status = "private"
            profile.updated_at = now

        await self.session.commit()
        return consent

    async def publish_profile(self, user_id: str) -> TalentProfile:
        profile = await self.get_profile_by_user_id(user_id)
        if not profile:
            raise ValueError("Profile not found")
        if not profile.headline:
            raise ValueError("Cannot publish without a headline")
        if not profile.listing_consent or not profile.listing_consent.opt_in_directory:
            raise ValueError("Explicit opt-in directory consent is required before publishing")

        profile.is_published = True
        profile.status = "active"
        profile.is_draft = False
        profile.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        return profile

    async def unpublish_profile(self, user_id: str) -> TalentProfile:
        profile = await self.get_profile_by_user_id(user_id)
        if not profile:
            raise ValueError("Profile not found")

        profile.is_published = False
        profile.status = "private"
        profile.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        return profile

    async def get_preview(self, user_id: str) -> dict[str, Any]:
        """Generate public preview for talent user, stripping private data."""
        profile = await self.get_profile_by_user_id(user_id)
        if not profile:
            raise ValueError("Profile not found")
        return self._format_public_profile(profile, is_owner=True)

    async def get_public_profile(self, profile_id: str) -> dict[str, Any] | None:
        """Fetch public profile by profile_id with strict privacy checks."""
        stmt = (
            select(TalentProfile)
            .where(TalentProfile.id == profile_id)
            .options(
                selectinload(TalentProfile.skills),
                selectinload(TalentProfile.artifacts),
                selectinload(TalentProfile.availability),
                selectinload(TalentProfile.rate_preference),
                selectinload(TalentProfile.listing_consent),
                selectinload(TalentProfile.verification_claims),
            )
        )
        res = await self.session.execute(stmt)
        profile = res.scalar_one_or_none()
        if not profile:
            return None

        # Must be published and opted in
        if not profile.is_published or not profile.listing_consent or not profile.listing_consent.opt_in_directory:
            return None
        if profile.status != "active":
            return None

        return self._format_public_profile(profile, is_owner=False)

    def _format_public_profile(self, profile: TalentProfile, is_owner: bool = False) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        # Check availability expiration
        avail = profile.availability
        avail_status = avail.status if avail else "unavailable"
        is_expired = False
        if avail and avail.expires_at:
            exp = avail.expires_at if avail.expires_at.tzinfo else avail.expires_at.replace(tzinfo=timezone.utc)
            if exp < now:
                avail_status = "expired"
                is_expired = True

        consent = profile.listing_consent
        contact_allowed = bool(consent and consent.allow_platform_contact)

        # Verified claims summary
        verified_claims = []
        for claim in profile.verification_claims:
            if claim.status == "verified":
                verified_claims.append({
                    "id": claim.id,
                    "claim_type": claim.claim_type,
                    "level": claim.level,
                    "claim_source": claim.claim_source,
                    "verified_at": claim.verified_at.isoformat() if claim.verified_at else None,
                })

        return {
            "id": profile.id,
            "headline": profile.headline,
            "bio": profile.bio,
            "primary_segment": profile.primary_segment,
            "years_experience": profile.years_experience,
            "location_display": profile.location_display,
            "is_published": profile.is_published,
            "status": profile.status,
            "is_sample": profile.is_sample,
            "contact_allowed": contact_allowed,
            "search_indexing_consent": bool(consent and consent.search_indexing_consent),
            "availability": {
                "status": avail_status,
                "hours_per_week": avail.hours_per_week if avail else 0,
                "expires_at": avail.expires_at.isoformat() if avail and avail.expires_at else None,
                "is_expired": is_expired,
            } if avail else None,
            "rate_preference": {
                "min_rate": profile.rate_preference.min_rate,
                "max_rate": profile.rate_preference.max_rate,
                "currency": profile.rate_preference.currency,
                "rate_type": profile.rate_preference.rate_type,
            } if profile.rate_preference else None,
            "skills": [
                {
                    "id": s.id,
                    "skill_name": s.skill_name,
                    "category": s.category,
                    "years_of_experience": s.years_of_experience,
                    "verification_status": s.verification_status,
                }
                for s in profile.skills
            ],
            "portfolio_artifacts": [
                {
                    "id": a.id,
                    "title": a.title,
                    "url": a.url,
                    "artifact_type": a.artifact_type,
                    "contribution_role": a.contribution_role,
                    "description": a.description,
                    "verification_status": a.verification_status,
                }
                for a in profile.artifacts
            ],
            "verified_claims": verified_claims,
            # Owner specific info
            "is_owner_view": is_owner,
            "listing_consent": {
                "opt_in_directory": consent.opt_in_directory,
                "allow_platform_contact": consent.allow_platform_contact,
                "search_indexing_consent": consent.search_indexing_consent,
                "consented_at": consent.consented_at.isoformat() if consent.consented_at else None,
            } if is_owner and consent else None,
        }
