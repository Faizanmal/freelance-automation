"""Phase 13 — Verified talent and employer network (marketplace foundation) API.

Feature flagged native marketplace kept private until Gate 18.
Includes:
- Freelancer profile editor (profile, skills, portfolio artifacts, availability, rates, consent)
- Public opt-in directory with privacy safeguards, non-discriminatory filters, X-Robots-Tag handling
- Employer organization onboarding, memberships, seat lifecycle & audit logs
- Verification levels (Level 1, 2, 3), sandbox provider, minimal scope OAuth & evidence correction
- Multi-component reputation evaluation (sample size threshold, newcomer exposure, time decay)
- Reports & appeals procedures
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from backend.application.services.network import (
    DiscoveryService,
    OrgService,
    ProfileService,
    ReportService,
    ReputationService,
    VerificationService,
)
from config.settings import get_settings
from database.core.session import get_db
from database.models.user import User
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status

router = APIRouter(prefix="/network", tags=["network"])
settings = get_settings()


def _enforce_marketplace_access(user: User | None = None) -> None:
    """Ensure marketplace feature flag is respected and private until Gate 18."""
    # When feature flag is disabled, only authenticated users in private preview can access
    if not settings.feature_marketplace_enabled:
        if settings.marketplace_status == "disabled":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Marketplace foundation is disabled.",
            )
        # In private preview, authenticated users can participate, but public anonymous activation is disabled
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Marketplace is in private preview (Gate 18 prerequisite). Sign in required to participate.",
            )


# -------------------------------------------------------------------------
# Request / Response Schemas
# -------------------------------------------------------------------------


class ProfileUpdatePayload(BaseModel):
    headline: str | None = Field(default=None, max_length=256)
    bio: str | None = Field(default=None, max_length=5000)
    primary_segment: str | None = Field(default="ai_software_automation", max_length=64)
    years_experience: float | None = Field(default=None, ge=0.0, le=70.0)
    location_display: str | None = Field(default=None, max_length=128)


class SkillPayload(BaseModel):
    skill_id: str | None = None
    skill_name: str = Field(min_length=1, max_length=128)
    category: str = Field(default="software", max_length=64)
    years_of_experience: float = Field(default=1.0, ge=0.1, le=50.0)


class ArtifactPayload(BaseModel):
    artifact_id: str | None = None
    title: str = Field(min_length=1, max_length=256)
    url: str = Field(min_length=4, max_length=512)
    artifact_type: Literal["github_repo", "case_study", "live_deployment", "code_sample"] = "github_repo"
    contribution_role: Literal["owner", "core_contributor", "contributor", "lead_architect"] = "contributor"
    description: str | None = Field(default=None, max_length=2000)


class AvailabilityPayload(BaseModel):
    status: Literal["available", "partially_available", "busy", "unavailable"] = "available"
    hours_per_week: int = Field(default=40, ge=1, le=168)
    available_from: datetime | None = None
    expires_at: datetime | None = None


class RatePayload(BaseModel):
    min_rate: float = Field(ge=0.0)
    max_rate: float | None = Field(default=None, ge=0.0)
    currency: str = Field(default="USD", min_length=3, max_length=8)
    rate_type: Literal["hourly", "fixed", "retainer"] = "hourly"


class ConsentPayload(BaseModel):
    opt_in_directory: bool = False
    allow_platform_contact: bool = False
    search_indexing_consent: bool = False


class OrgCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    website: str | None = Field(default=None, max_length=256)
    industry: str = Field(default="technology", max_length=128)
    org_domain: str | None = Field(default=None, max_length=128)
    is_sample: bool = False


class OrgInvitePayload(BaseModel):
    email: str = Field(min_length=3, max_length=256)
    role: Literal["admin", "hiring_manager", "member"] = "member"


class OrgRoleUpdatePayload(BaseModel):
    role: Literal["admin", "hiring_manager", "member"]


class ClaimCreatePayload(BaseModel):
    claim_type: Literal[
        "email_domain",
        "org_representative",
        "github_contribution",
        "portfolio_artifact",
        "skill_assessment",
    ]
    profile_id: str | None = None
    reviewer_notes: str | None = Field(default=None, max_length=1000)


class EvidenceSubmitPayload(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    evidence_type: str = Field(min_length=1, max_length=64)
    provider_reference_id: str | None = Field(default=None, max_length=256)
    evidence_payload: dict[str, Any] = Field(default_factory=dict)


class EvidenceCorrectionPayload(BaseModel):
    correction_notes: str = Field(min_length=1, max_length=2000)
    updated_payload: dict[str, Any] | None = None
    updated_reference_id: str | None = Field(default=None, max_length=256)


class SandboxVerifyPayload(BaseModel):
    user_handle_or_email: str = Field(min_length=1, max_length=256)
    target_resource: str = Field(min_length=1, max_length=512)
    claimed_role: str = Field(default="contributor", max_length=64)


class ReportPayload(BaseModel):
    target_type: Literal["talent_profile", "org_profile", "verification_claim", "evidence"]
    target_id: str = Field(min_length=1, max_length=36)
    report_type: Literal["report", "appeal"] = "report"
    reason: str = Field(min_length=1, max_length=128)
    details: str = Field(min_length=1, max_length=5000)


# -------------------------------------------------------------------------
# Freelancer Profile Endpoints
# -------------------------------------------------------------------------


@router.get("/profile")
async def get_my_profile(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProfileService(session)
    preview = await service.get_preview(user.id)
    return {"profile": preview}


@router.put("/profile")
async def update_my_profile(
    payload: ProfileUpdatePayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProfileService(session)
    try:
        profile = await service.update_profile_details(
            user_id=user.id,
            headline=payload.headline,
            bio=payload.bio,
            primary_segment=payload.primary_segment,
            years_experience=payload.years_experience,
            location_display=payload.location_display,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"message": "Profile updated", "profile_id": profile.id}


@router.post("/profile/skills")
async def add_or_update_my_skill(
    payload: SkillPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProfileService(session)
    try:
        skill = await service.add_or_update_skill(
            user_id=user.id,
            skill_name=payload.skill_name,
            category=payload.category,
            years_of_experience=payload.years_of_experience,
            skill_id=payload.skill_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {
        "message": "Skill saved",
        "skill": {
            "id": skill.id,
            "skill_name": skill.skill_name,
            "category": skill.category,
            "years_of_experience": skill.years_of_experience,
            "verification_status": skill.verification_status,
        },
    }


@router.delete("/profile/skills/{skill_id}")
async def delete_my_skill(
    skill_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProfileService(session)
    success = await service.remove_skill(user.id, skill_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    return {"message": "Skill removed"}


@router.post("/profile/artifacts")
async def add_or_update_my_artifact(
    payload: ArtifactPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProfileService(session)
    try:
        artifact = await service.add_or_update_artifact(
            user_id=user.id,
            title=payload.title,
            url=payload.url,
            artifact_type=payload.artifact_type,
            contribution_role=payload.contribution_role,
            description=payload.description,
            artifact_id=payload.artifact_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {
        "message": "Artifact saved",
        "artifact": {
            "id": artifact.id,
            "title": artifact.title,
            "url": artifact.url,
            "artifact_type": artifact.artifact_type,
            "contribution_role": artifact.contribution_role,
            "verification_status": artifact.verification_status,
        },
    }


@router.delete("/profile/artifacts/{artifact_id}")
async def delete_my_artifact(
    artifact_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProfileService(session)
    success = await service.remove_artifact(user.id, artifact_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    return {"message": "Artifact removed"}


@router.put("/profile/availability")
async def update_my_availability(
    payload: AvailabilityPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProfileService(session)
    try:
        avail = await service.update_availability(
            user_id=user.id,
            status=payload.status,
            hours_per_week=payload.hours_per_week,
            available_from=payload.available_from,
            expires_at=payload.expires_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {
        "message": "Availability updated",
        "availability": {
            "status": avail.status,
            "hours_per_week": avail.hours_per_week,
            "expires_at": avail.expires_at.isoformat() if avail.expires_at else None,
        },
    }


@router.put("/profile/rates")
async def update_my_rates(
    payload: RatePayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProfileService(session)
    try:
        rates = await service.update_rate_preference(
            user_id=user.id,
            min_rate=payload.min_rate,
            max_rate=payload.max_rate,
            currency=payload.currency,
            rate_type=payload.rate_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {
        "message": "Rate preference updated",
        "rates": {
            "min_rate": rates.min_rate,
            "max_rate": rates.max_rate,
            "currency": rates.currency,
            "rate_type": rates.rate_type,
        },
    }


@router.put("/profile/consent")
async def update_my_consent(
    payload: ConsentPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProfileService(session)
    consent = await service.update_listing_consent(
        user_id=user.id,
        opt_in_directory=payload.opt_in_directory,
        allow_platform_contact=payload.allow_platform_contact,
        search_indexing_consent=payload.search_indexing_consent,
    )
    return {
        "message": "Privacy consent updated",
        "consent": {
            "opt_in_directory": consent.opt_in_directory,
            "allow_platform_contact": consent.allow_platform_contact,
            "search_indexing_consent": consent.search_indexing_consent,
            "consented_at": consent.consented_at.isoformat() if consent.consented_at else None,
        },
    }


@router.post("/profile/publish")
async def publish_my_profile(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProfileService(session)
    try:
        profile = await service.publish_profile(user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"message": "Profile published to opt-in directory", "status": profile.status}


@router.post("/profile/unpublish")
async def unpublish_my_profile(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProfileService(session)
    profile = await service.unpublish_profile(user.id)
    return {"message": "Profile unpublished and hidden", "status": profile.status}


@router.get("/profile/preview")
async def preview_my_profile(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProfileService(session)
    preview = await service.get_preview(user.id)
    return {"preview": preview}


# -------------------------------------------------------------------------
# Public Opt-in Directory Endpoints
# -------------------------------------------------------------------------


@router.get("/directory")
async def search_directory(
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    skills: list[str] = Query(default=[]),
    work_type: str | None = Query(default=None),
    min_rate: float | None = Query(default=None),
    max_rate: float | None = Query(default=None),
    currency: str | None = Query(default=None),
    availability: str | None = Query(default=None),
    min_level: int | None = Query(default=None),
    primary_segment: str | None = Query(default=None),
    include_sample: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    _enforce_marketplace_access(user)

    # Search indexing policy: Always set noindex, nofollow while in private preview or by default
    response.headers["X-Robots-Tag"] = "noindex, nofollow"

    service = DiscoveryService(session)
    results = await service.search_directory(
        skills=skills,
        work_type=work_type,
        min_rate=min_rate,
        max_rate=max_rate,
        currency=currency,
        availability_status=availability,
        min_verification_level=min_level,
        primary_segment=primary_segment,
        include_sample=include_sample,
        limit=limit,
        offset=offset,
    )
    return results


@router.get("/directory/{profile_id}")
async def get_public_profile(
    profile_id: str,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProfileService(session)
    profile = await service.get_public_profile(profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Talent profile not found or not published to directory.",
        )

    # If search indexing is not consented, enforce noindex
    if not profile.get("search_indexing_consent") or not settings.feature_marketplace_enabled:
        response.headers["X-Robots-Tag"] = "noindex, nofollow"

    return {"talent": profile}


# -------------------------------------------------------------------------
# Employer Organizations & Seat Lifecycle Endpoints
# -------------------------------------------------------------------------


@router.post("/organizations", status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrgCreatePayload,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = OrgService(session)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        org = await service.create_organization(
            owner_id=user.id,
            name=payload.name,
            website=payload.website,
            industry=payload.industry,
            org_domain=payload.org_domain,
            is_sample=payload.is_sample,
            ip_address=client_ip,
            user_agent=user_agent,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "message": "Organization created",
        "organization": {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "industry": org.industry,
            "org_domain": org.org_domain,
            "domain_verified": org.domain_verified,
            "verification_status": org.verification_status,
        },
    }


@router.get("/organizations")
async def list_my_organizations(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = OrgService(session)
    orgs = await service.get_user_organizations(user.id)
    return {"organizations": orgs}


@router.get("/organizations/{org_id}")
async def get_organization_details(
    org_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = OrgService(session)
    try:
        mem = await service.verify_user_org_permission(org_id, user.id)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    org = await service.get_org_by_id(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    members = [
        {
            "id": m.id,
            "user_id": m.user_id,
            "email": m.email,
            "role": m.role,
            "seat_status": m.seat_status,
            "invitation_token": m.invitation_token if mem.role in {"owner", "admin"} else None,
            "invited_at": m.invited_at.isoformat() if m.invited_at else None,
            "accepted_at": m.accepted_at.isoformat() if m.accepted_at else None,
            "revoked_at": m.revoked_at.isoformat() if m.revoked_at else None,
        }
        for m in org.members
    ]

    return {
        "organization": {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "website": org.website,
            "industry": org.industry,
            "org_domain": org.org_domain,
            "domain_verified": org.domain_verified,
            "verification_status": org.verification_status,
            "my_role": mem.role,
            "members": members,
        }
    }


@router.post("/organizations/{org_id}/invitations")
async def invite_org_member(
    org_id: str,
    payload: OrgInvitePayload,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = OrgService(session)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        membership = await service.invite_member(
            org_id=org_id,
            actor_id=user.id,
            email=payload.email,
            role=payload.role,
            ip_address=client_ip,
            user_agent=user_agent,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "message": "Invitation sent",
        "invitation": {
            "membership_id": membership.id,
            "email": membership.email,
            "role": membership.role,
            "seat_status": membership.seat_status,
            "invitation_token": membership.invitation_token,
        },
    }


@router.post("/organizations/invitations/{token}/accept")
async def accept_org_invitation(
    token: str,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = OrgService(session)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        membership = await service.accept_invitation(
            invitation_token=token,
            user=user,
            ip_address=client_ip,
            user_agent=user_agent,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "message": "Invitation accepted",
        "organization_id": membership.org_id,
        "role": membership.role,
        "seat_status": membership.seat_status,
    }


@router.put("/organizations/{org_id}/members/{membership_id}")
async def update_org_member_role(
    org_id: str,
    membership_id: str,
    payload: OrgRoleUpdatePayload,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = OrgService(session)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        mem = await service.update_member_role(
            org_id=org_id,
            actor_id=user.id,
            membership_id=membership_id,
            new_role=payload.role,
            ip_address=client_ip,
            user_agent=user_agent,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Member role updated", "role": mem.role}


@router.delete("/organizations/{org_id}/members/{membership_id}")
async def revoke_org_seat(
    org_id: str,
    membership_id: str,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = OrgService(session)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        mem = await service.revoke_seat(
            org_id=org_id,
            actor_id=user.id,
            membership_id=membership_id,
            ip_address=client_ip,
            user_agent=user_agent,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Member seat revoked", "seat_status": mem.seat_status}


@router.get("/organizations/{org_id}/audit-logs")
async def get_org_audit_logs(
    org_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = OrgService(session)
    try:
        logs = await service.get_org_audit_logs(org_id, user.id, limit=limit)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    return {"audit_logs": logs}


# -------------------------------------------------------------------------
# Verification & Sandbox Providers Endpoints
# -------------------------------------------------------------------------


@router.post("/verification/claims")
async def create_verification_claim(
    payload: ClaimCreatePayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = VerificationService(session)
    try:
        claim = await service.create_claim(
            user_id=user.id,
            claim_type=payload.claim_type,
            profile_id=payload.profile_id,
            reviewer_notes=payload.reviewer_notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "message": "Verification claim created",
        "claim": {
            "id": claim.id,
            "claim_type": claim.claim_type,
            "level": claim.level,
            "claim_source": claim.claim_source,
            "status": claim.status,
        },
    }


@router.post("/verification/claims/{claim_id}/evidence")
async def submit_verification_evidence(
    claim_id: str,
    payload: EvidenceSubmitPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = VerificationService(session)
    try:
        evidence = await service.submit_evidence(
            claim_id=claim_id,
            user_id=user.id,
            provider=payload.provider,
            evidence_type=payload.evidence_type,
            evidence_payload=payload.evidence_payload,
            provider_reference_id=payload.provider_reference_id,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Evidence submitted for review", "evidence_id": evidence.id}


@router.put("/verification/evidence/{evidence_id}/correction")
async def correct_verification_evidence(
    evidence_id: str,
    payload: EvidenceCorrectionPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = VerificationService(session)
    try:
        evidence = await service.correct_evidence(
            evidence_id=evidence_id,
            user_id=user.id,
            correction_notes=payload.correction_notes,
            updated_payload=payload.updated_payload,
            updated_reference_id=payload.updated_reference_id,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Evidence corrected", "evidence_id": evidence.id}


@router.post("/verification/claims/{claim_id}/sandbox-verify")
async def run_sandbox_verification(
    claim_id: str,
    payload: SandboxVerifyPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = VerificationService(session)
    try:
        res = await service.process_sandbox_verification(
            claim_id=claim_id,
            actor_id=user.id,
            user_handle_or_email=payload.user_handle_or_email,
            target_resource=payload.target_resource,
            claimed_role=payload.claimed_role,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return res


# -------------------------------------------------------------------------
# Reputation & Moderation Endpoints
# -------------------------------------------------------------------------


@router.get("/reputation/{user_or_org_id}")
async def get_reputation(
    user_or_org_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    entity_type: Literal["freelancer", "employer"] = "freelancer",
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ReputationService(session)
    rep = await service.evaluate_reputation(user_or_org_id, entity_type=entity_type)
    return {"reputation": rep}


@router.post("/reports")
async def submit_marketplace_report(
    payload: ReportPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ReportService(session)
    try:
        report = await service.submit_report_or_appeal(
            reporter_id=user.id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            reason=payload.reason,
            details=payload.details,
            report_type=payload.report_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Report or appeal submitted", "report_id": report.id, "status": report.status}
