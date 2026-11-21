"""Phase 08 — Freelancer CRM / pipeline / durable copilot runs."""

from __future__ import annotations

from datetime import datetime
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
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.core.base import Base

# Explicit pipeline stages (acceptance). `applied` = applied/contacted.
PIPELINE_STAGES = (
    "discovered",
    "saved",
    "researching",
    "ready",
    "applied",
    "interview",
    "negotiating",
    "won",
    "lost",
    "archived",
)

# Legacy UserLeadAction.status ↔ pipeline_stage
STATUS_TO_STAGE: dict[str, str] = {
    "save": "saved",
    "skip": "archived",
    "pitched": "applied",
    "won": "won",
}
STAGE_TO_STATUS: dict[str, str] = {
    "discovered": "save",  # soft: keep visible engagement
    "saved": "save",
    "researching": "save",
    "ready": "save",
    "applied": "pitched",
    "interview": "pitched",
    "negotiating": "pitched",
    "won": "won",
    "lost": "skip",
    "archived": "skip",
}

COPILOT_INTENTS = (
    "lead_brief",
    "requirements_gap",
    "portfolio_selection",
    "proposal_draft",
    "interview_prep",
    "scope_clarification",
    "negotiation_scenario",
)

AGENT_RUN_STATES = (
    "queued",
    "running",
    "awaiting_confirmation",
    "succeeded",
    "failed",
    "cancelled",
    "timed_out",
)

# Allowlisted tools — no unrestricted shell/browser/account access.
COPILOT_TOOLS = (
    "read_profile",
    "read_job",
    "read_lead",
    "read_portfolio_summary",
    "list_drafts",
    "save_draft_preview",  # preview only; never sends
)


class LeadStageEvent(Base):
    """Append-only stage history for a lead action."""

    __tablename__ = "lead_stage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_action_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_lead_actions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_stage: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="user"
    )  # user | system | migrate | undo
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), index=True
    )


class LeadNote(Base):
    __tablename__ = "lead_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_action_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_lead_actions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="note"
    )  # note | negotiation | research
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class LeadTask(Base):
    __tablename__ = "lead_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_action_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_lead_actions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class LeadReminder(Base):
    """User-controlled reminders; unique key prevents duplicate active reminders."""

    __tablename__ = "lead_reminders"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "lead_action_id",
            "remind_at",
            "kind",
            name="uq_lead_reminder_slot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_action_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_lead_actions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="follow_up"
    )
    remind_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )


class CopilotDraft(Base):
    """Editable, versioned drafts — never sent without explicit user action."""

    __tablename__ = "copilot_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_action_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_lead_actions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_run_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    intent: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    unverified_claims: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # only after explicit outward action elsewhere
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AgentRun(Base):
    """Durable copilot / agent run with budgets, cancellation, retries."""

    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    lead_action_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_lead_actions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    intent: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued", index=True
    )
    input_refs: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="copilot_v1"
    )
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    budget_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=4000)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    parent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), index=True
    )

    tool_calls = relationship(
        "AgentToolCall",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AgentToolCall(Base):
    """Redacted tool call history for an agent run."""

    __tablename__ = "agent_tool_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    args_redacted: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result_redacted: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )

    run = relationship("AgentRun", back_populates="tool_calls")


class PipelineUndoEvent(Base):
    """Short-lived undo buffer for safe internal bulk/stage actions."""

    __tablename__ = "pipeline_undo_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
