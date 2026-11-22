"""Phase 14 — Client workspace, native project listings, hiring intent and moderation queue.

Revision ID: 20261127_client_project_hiring_intent_phase14
Revises: 20261126_talent_employer_network_phase13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261127_client_project_hiring_intent_phase14"
down_revision = "20261126_talent_employer_network_phase13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Native Projects
    op.create_table(
        "native_projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("employer_organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("creator_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("raw_description", sa.Text(), nullable=False),
        sa.Column("ai_scope_summary", sa.Text(), nullable=True),
        sa.Column("ai_clarification_approved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("primary_segment", sa.String(length=64), nullable=False, server_default="ai_software_automation"),
        sa.Column("scope_level", sa.String(length=32), nullable=False, server_default="medium"),
        sa.Column("work_type", sa.String(length=32), nullable=False, server_default="remote"),
        sa.Column("commitment_type", sa.String(length=32), nullable=False, server_default="contract"),
        sa.Column("required_hours_per_week", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("skills_required", sa.JSON(), nullable=False),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=False),
        sa.Column("milestone_outline", sa.JSON(), nullable=False),
        sa.Column("budget_min", sa.Float(), nullable=False),
        sa.Column("budget_max", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="USD"),
        sa.Column("rate_period", sa.String(length=32), nullable=False, server_default="fixed"),
        sa.Column("budget_basis_notes", sa.Text(), nullable=True),
        sa.Column("hiring_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reconfirm_by", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_reconfirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("payment_provider_ref", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("review_state", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("flagged_reason", sa.String(length=256), nullable=True),
        sa.Column("abandonment_reason", sa.String(length=256), nullable=True),
        sa.Column("duplicate_hash", sa.String(length=64), nullable=True),
        sa.Column("is_sample", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_native_projects_org_id", "native_projects", ["org_id"])
    op.create_index("ix_native_projects_creator_id", "native_projects", ["creator_id"])
    op.create_index("ix_native_projects_duplicate_hash", "native_projects", ["duplicate_hash"])

    # 2. Project Status Histories
    op.create_table(
        "project_status_histories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("native_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.String(length=256), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_project_status_histories_project_id", "project_status_histories", ["project_id"])

    # 3. Project Clarification Requests
    op.create_table(
        "project_clarification_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("native_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("freelancer_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_project_clarification_requests_project_id", "project_clarification_requests", ["project_id"])
    op.create_index("ix_project_clarification_requests_freelancer_id", "project_clarification_requests", ["freelancer_id"])

    # 4. Project Candidate Shortlists
    op.create_table(
        "project_candidate_shortlists",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("native_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="shortlisted"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_project_candidate_shortlists_project_id", "project_candidate_shortlists", ["project_id"])
    op.create_index("ix_project_candidate_shortlists_candidate_id", "project_candidate_shortlists", ["candidate_id"])

    # 5. Project Moderation Queue
    op.create_table(
        "project_moderation_queue",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("native_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("flagged_by", sa.String(length=32), nullable=False, server_default="ai_safety_scanner"),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("evidence_summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_review"),
        sa.Column("reviewer_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("appeal_details", sa.Text(), nullable=True),
        sa.Column("appealed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_project_moderation_queue_project_id", "project_moderation_queue", ["project_id"])


def downgrade() -> None:
    op.drop_table("project_moderation_queue")
    op.drop_table("project_candidate_shortlists")
    op.drop_table("project_clarification_requests")
    op.drop_table("project_status_histories")
    op.drop_table("native_projects")
