"""Phase 15 — Fair two-sided marketplace, matching, mutual-interest applications, messaging, and concurrency-safe offers.

Models:
- ProjectInvitation
- ProjectApplication
- ProjectConversation
- ProjectMessage
- ProjectOffer
- ProjectOfferRevision
- ProjectMatchScore
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

APPLICATION_STATUSES = (
    "submitted",
    "shortlisted",
    "negotiating",
    "offered",
    "accepted",
    "declined",
    "withdrawn",
    "rejected",
)

OFFER_STATUSES = (
    "pending_review",
    "accepted",
    "declined",
    "superseded",
    "expired",
    "canceled",
)

INVITATION_STATUSES = (
    "pending",
    "accepted",
    "declined",
    "expired",
)


class ProjectInvitation(Base):
    """Client invitation extended to a freelancer profile to consider a native project."""

    __tablename__ = "project_invitations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("native_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("employer_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    freelancer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
    )
    decline_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    project = relationship("NativeProject", foreign_keys=[project_id])
    org = relationship("EmployerOrg", foreign_keys=[org_id])
    freelancer = relationship("User", foreign_keys=[freelancer_id])


class ProjectApplication(Base):
    """Freelancer expression of mutual interest with structured response (100% free, no unpaid custom work)."""

    __tablename__ = "project_applications"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
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
    status: Mapped[str] = mapped_column(
        String(32),
        default="submitted",
        nullable=False,
        index=True,
    )
    structured_pitch: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    relevant_artifacts: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    proposed_rate: Mapped[float] = mapped_column(Float, nullable=False)
    proposed_rate_period: Mapped[str] = mapped_column(
        String(32),
        default="fixed",
        nullable=False,
    )
    estimated_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    project = relationship("NativeProject", foreign_keys=[project_id])
    freelancer = relationship("User", foreign_keys=[freelancer_id])
    conversations = relationship("ProjectConversation", back_populates="application")
    offers = relationship("ProjectOffer", back_populates="application")


class ProjectConversation(Base):
    """Direct authenticated messaging channel for project scope negotiation."""

    __tablename__ = "project_conversations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("native_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("employer_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    freelancer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("project_applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    project = relationship("NativeProject", foreign_keys=[project_id])
    org = relationship("EmployerOrg", foreign_keys=[org_id])
    freelancer = relationship("User", foreign_keys=[freelancer_id])
    application = relationship("ProjectApplication", back_populates="conversations")
    messages = relationship("ProjectMessage", back_populates="conversation", cascade="all, delete-orphan")


class ProjectMessage(Base):
    """Authenticated message within a project negotiation conversation."""

    __tablename__ = "project_messages"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_role: Mapped[str] = mapped_column(
        String(32),  # 'client', 'freelancer', 'system'
        nullable=False,
    )
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    flagged_as_spam: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    conversation = relationship("ProjectConversation", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])


class ProjectOffer(Base):
    """Bilateral project offer with milestone agreements and concurrency locking."""

    __tablename__ = "project_offers"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("native_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("project_conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("employer_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    freelancer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    creator_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    creator_role: Mapped[str] = mapped_column(
        String(32),  # 'client', 'freelancer'
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending_review",
        nullable=False,
        index=True,
    )
    contract_type: Mapped[str] = mapped_column(
        String(32),  # 'fixed_price', 'hourly', 'monthly_retainer'
        default="fixed_price",
        nullable=False,
    )
    agreed_amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    milestones: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    scope_summary: Mapped[str] = mapped_column(Text, nullable=False)
    decision_deadline: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    lock_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    project = relationship("NativeProject", foreign_keys=[project_id])
    application = relationship("ProjectApplication", back_populates="offers")
    org = relationship("EmployerOrg", foreign_keys=[org_id])
    freelancer = relationship("User", foreign_keys=[freelancer_id])
    creator = relationship("User", foreign_keys=[creator_id])
    revisions = relationship("ProjectOfferRevision", back_populates="offer", cascade="all, delete-orphan")


class ProjectOfferRevision(Base):
    """Audit log of offer counter-proposals and scope/milestone revisions."""

    __tablename__ = "project_offer_revisions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    offer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project_offers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    author_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_role: Mapped[str] = mapped_column(String(32), nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    contract_type: Mapped[str] = mapped_column(String(32), nullable=False)
    agreed_amount: Mapped[float] = mapped_column(Float, nullable=False)
    milestones: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    scope_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    offer = relationship("ProjectOffer", back_populates="revisions")
    author = relationship("User", foreign_keys=[author_id])


class ProjectMatchScore(Base):
    """Deterministic match evaluation and explanation score for project-talent pairing."""

    __tablename__ = "project_match_scores"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
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
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    skill_score: Mapped[float] = mapped_column(Float, nullable=False)
    budget_score: Mapped[float] = mapped_column(Float, nullable=False)
    availability_score: Mapped[float] = mapped_column(Float, nullable=False)
    work_pref_score: Mapped[float] = mapped_column(Float, nullable=False)
    newcomer_boost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    breakdown_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    missing_information_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    hard_filter_passed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    project = relationship("NativeProject", foreign_keys=[project_id])
    freelancer = relationship("User", foreign_keys=[freelancer_id])
