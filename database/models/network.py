"""Phase 13 — Verified talent and employer network (marketplace foundation).

Additive domain models:
- TalentProfile
- TalentSkill
- PortfolioArtifact
- WorkAvailability
- RatePreference
- PublicListingConsent
- EmployerOrg
- OrgMembership
- OrgSeatLog
- VerificationClaim
- VerificationEvidence
- MarketplaceReport
- ReputationActivity
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.core.base import Base


class TalentProfile(Base):
    __tablename__ = "talent_profiles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    headline: Mapped[str] = mapped_column(String(256), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_segment: Mapped[str] = mapped_column(
        String(64), nullable=False, default="ai_software_automation", server_default="ai_software_automation"
    )
    years_experience: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    location_display: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="private", server_default="private"
    )  # draft, private, active, suspended, archived
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    skills = relationship("TalentSkill", back_populates="profile", cascade="all, delete-orphan")
    artifacts = relationship("PortfolioArtifact", back_populates="profile", cascade="all, delete-orphan")
    availability = relationship("WorkAvailability", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    rate_preference = relationship("RatePreference", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    listing_consent = relationship("PublicListingConsent", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    verification_claims = relationship("VerificationClaim", back_populates="profile", cascade="all, delete-orphan")


class TalentSkill(Base):
    __tablename__ = "talent_skills"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("talent_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    category: Mapped[str] = mapped_column(
        String(64), nullable=False, default="software", server_default="software"
    )
    years_of_experience: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unverified", server_default="unverified"
    )  # unverified, claimed, evidence_submitted, verified, rejected
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    profile = relationship("TalentProfile", back_populates="skills")


class PortfolioArtifact(Base):
    __tablename__ = "portfolio_artifacts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("talent_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="github_repo", server_default="github_repo"
    )  # github_repo, case_study, live_deployment, code_sample
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    # Contribution role: owner, core_contributor, contributor, lead_architect
    contribution_role: Mapped[str] = mapped_column(
        String(64), nullable=False, default="contributor", server_default="contributor"
    )
    verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unverified", server_default="unverified"
    )  # unverified, claimed, verified, rejected
    evidence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    profile = relationship("TalentProfile", back_populates="artifacts")


class WorkAvailability(Base):
    __tablename__ = "talent_availabilities"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("talent_profiles.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="available", server_default="available"
    )  # available, partially_available, busy, unavailable
    hours_per_week: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    available_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )  # Clear availability expiry!
    last_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    profile = relationship("TalentProfile", back_populates="availability")


class RatePreference(Base):
    __tablename__ = "talent_rates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("talent_profiles.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    min_rate: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    max_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(
        String(8), nullable=False, default="USD", server_default="USD"
    )
    rate_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="hourly", server_default="hourly"
    )  # hourly, fixed, retainer
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    profile = relationship("TalentProfile", back_populates="rate_preference")


class PublicListingConsent(Base):
    __tablename__ = "talent_listing_consents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("talent_profiles.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    opt_in_directory: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # Private by default
    allow_platform_contact: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # Contact via platform only if opted in
    search_indexing_consent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # Search indexing consent
    consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    profile = relationship("TalentProfile", back_populates="listing_consent")


class EmployerOrg(Base):
    __tablename__ = "employer_organizations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    website: Mapped[str | None] = mapped_column(String(256), nullable=True)
    industry: Mapped[str] = mapped_column(
        String(128), nullable=False, default="technology", server_default="technology"
    )
    org_domain: Mapped[str | None] = mapped_column(String(128), nullable=True)
    domain_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unverified", server_default="unverified"
    )  # unverified, domain_verified, identity_verified, rejected
    owner_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    owner = relationship("User", foreign_keys=[owner_id])
    members = relationship("OrgMembership", back_populates="org", cascade="all, delete-orphan")
    seat_logs = relationship("OrgSeatLog", back_populates="org", cascade="all, delete-orphan")


class OrgMembership(Base):
    __tablename__ = "employer_memberships"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("employer_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default="member", server_default="member"
    )  # owner, admin, hiring_manager, member
    seat_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="invited", server_default="invited"
    )  # invited, active, suspended, revoked
    invitation_token: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True, index=True
    )
    invited_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    org = relationship("EmployerOrg", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])
    invited_by = relationship("User", foreign_keys=[invited_by_id])


class OrgSeatLog(Base):
    __tablename__ = "employer_seat_audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("employer_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    target_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # invite_sent, invite_accepted, role_changed, seat_revoked, seat_suspended, access_granted
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )

    org = relationship("EmployerOrg", back_populates="seat_logs")
    actor = relationship("User", foreign_keys=[actor_id])
    target_user = relationship("User", foreign_keys=[target_user_id])


class VerificationClaim(Base):
    __tablename__ = "verification_claims"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("talent_profiles.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    claim_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # email_domain, org_representative, github_contribution, portfolio_artifact, skill_assessment
    level: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )  # 1: email/domain, 2: org rep/identity, 3: portfolio/skill
    claim_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="user_claimed", server_default="user_claimed"
    )  # user_claimed, independently_verified
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )  # pending, under_review, verified, rejected, revoked
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", foreign_keys=[user_id])
    profile = relationship("TalentProfile", back_populates="verification_claims")
    evidences = relationship("VerificationEvidence", back_populates="claim", cascade="all, delete-orphan")


class VerificationEvidence(Base):
    __tablename__ = "verification_evidences"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    claim_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("verification_claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # sandbox_provider, mock_github, domain_dns, portfolio_check
    evidence_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # oauth_grant, domain_txt_record, commit_history, artifact_inspection
    # Never collect government ID directly! Only store necessary provider references/status.
    provider_reference_id: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
    evidence_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    corrected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    correction_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    claim = relationship("VerificationClaim", back_populates="evidences")


class MarketplaceReport(Base):
    __tablename__ = "marketplace_reports_and_appeals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    reporter_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # talent_profile, org_profile, verification_claim, evidence
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="report", server_default="report"
    )  # report, appeal
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="opened", server_default="opened"
    )  # opened, in_review, resolved, dismissed
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    reporter = relationship("User", foreign_keys=[reporter_user_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])


class ReputationActivity(Base):
    __tablename__ = "reputation_activities"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    counterparty_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    entity_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="freelancer", server_default="freelancer"
    )  # freelancer, employer
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # response_recorded, delivery_confirmed, repeat_hire, paid_transaction, dispute_resolved
    transaction_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    response_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    is_verified_event: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_suspicious: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    decay_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    user = relationship("User", foreign_keys=[user_id])
    counterparty = relationship("User", foreign_keys=[counterparty_id])
