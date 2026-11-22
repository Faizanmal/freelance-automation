"""Phase 14 — Native client project brief, hiring intent evidence, lifecycle, and moderation models.

Models:
- NativeProject
- ProjectStatusHistory
- ProjectClarificationRequest
- ProjectCandidateShortlist
- ProjectModerationQueue
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.core.base import Base

PROJECT_LIFECYCLE_STAGES = (
    "draft",
    "submitted",
    "needs_clarification",
    "approved_open",
    "shortlist",
    "interviewing",
    "offered_hired",
    "closed",
    "canceled",
    "expired",
)

PROJECT_LEGAL_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"submitted", "canceled"},
    "submitted": {"needs_clarification", "approved_open", "canceled"},
    "needs_clarification": {"submitted", "canceled"},
    "approved_open": {"shortlist", "canceled", "expired", "closed"},
    "shortlist": {"interviewing", "approved_open", "canceled", "expired", "closed"},
    "interviewing": {"offered_hired", "shortlist", "canceled", "closed"},
    "offered_hired": {"closed"},
    "closed": {"approved_open"},  # Reopen
    "canceled": {"approved_open"},  # Reopen
    "expired": {"approved_open"},  # Reopen / refresh deadline
}

REVIEW_STATES = (
    "draft",
    "pending_review",
    "approved",
    "changes_requested",
    "flagged_for_human_review",
)


class NativeProject(Base):
    __tablename__ = "native_projects"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("employer_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    creator_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    raw_description: Mapped[str] = mapped_column(Text, nullable=False)
    ai_scope_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_clarification_approved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    primary_segment: Mapped[str] = mapped_column(
        String(64), nullable=False, default="ai_software_automation", server_default="ai_software_automation"
    )
    scope_level: Mapped[str] = mapped_column(
        String(32), nullable=False, default="medium", server_default="medium"
    )  # small, medium, large, enterprise
    work_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="remote", server_default="remote"
    )  # remote, hybrid, onsite
    commitment_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="contract", server_default="contract"
    )  # contract, full_time, part_time
    required_hours_per_week: Mapped[int] = mapped_column(
        Integer, nullable=False, default=20
    )
    skills_required: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    acceptance_criteria: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    milestone_outline: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    budget_min: Mapped[float] = mapped_column(Float, nullable=False)
    budget_max: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(8), nullable=False, default="USD", server_default="USD"
    )
    rate_period: Mapped[str] = mapped_column(
        String(32), nullable=False, default="fixed", server_default="fixed"
    )  # hourly, fixed, monthly_retainer
    budget_basis_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    hiring_deadline: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reconfirm_by: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_reconfirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payment_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # Unverified payment must NEVER appear funded
    payment_provider_ref: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default="draft"
    )
    review_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default="draft"
    )
    flagged_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    abandonment_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    duplicate_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
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

    # Relationships
    org = relationship("EmployerOrg", foreign_keys=[org_id])
    creator = relationship("User", foreign_keys=[creator_id])
    status_history = relationship(
        "ProjectStatusHistory", back_populates="project", cascade="all, delete-orphan"
    )
    clarification_requests = relationship(
        "ProjectClarificationRequest", back_populates="project", cascade="all, delete-orphan"
    )
    shortlisted_candidates = relationship(
        "ProjectCandidateShortlist", back_populates="project", cascade="all, delete-orphan"
    )
    moderation_queue_entries = relationship(
        "ProjectModerationQueue", back_populates="project", cascade="all, delete-orphan"
    )


class ProjectStatusHistory(Base):
    __tablename__ = "project_status_histories"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("native_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )

    project = relationship("NativeProject", back_populates="status_history")
    actor = relationship("User", foreign_keys=[actor_id])


class ProjectClarificationRequest(Base):
    __tablename__ = "project_clarification_requests"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("native_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    freelancer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )  # pending, answered, dismissed, reported
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    project = relationship("NativeProject", back_populates="clarification_requests")
    freelancer = relationship("User", foreign_keys=[freelancer_id])


class ProjectCandidateShortlist(Base):
    __tablename__ = "project_candidate_shortlists"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("native_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage: Mapped[str] = mapped_column(
        String(32), nullable=False, default="shortlisted", server_default="shortlisted"
    )  # shortlisted, interviewing, offered, hired, declined
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    project = relationship("NativeProject", back_populates="shortlisted_candidates")
    candidate = relationship("User", foreign_keys=[candidate_id])


class ProjectModerationQueue(Base):
    __tablename__ = "project_moderation_queue"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("native_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    flagged_by: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ai_safety_scanner", server_default="ai_safety_scanner"
    )  # ai_safety_scanner, user_report, manual_audit
    reason_code: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # discriminatory_criteria, malicious_link, upfront_fee_request, excessive_unpaid_work, missing_budget, duplicate_spam
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending_review", server_default="pending_review"
    )  # pending_review, under_review, approved, rejected, appealed, appeal_resolved
    reviewer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    appeal_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    appealed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )

    project = relationship("NativeProject", back_populates="moderation_queue_entries")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
