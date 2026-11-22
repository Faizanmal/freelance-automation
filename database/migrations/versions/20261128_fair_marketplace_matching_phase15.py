"""Phase 15 — Fair two-sided marketplace, matching, mutual-interest applications, messaging, and offers.

Revision ID: 20261128_fair_marketplace_matching_phase15
Revises: 20261127_client_project_hiring_intent_phase14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261128_fair_marketplace_matching_phase15"
down_revision = "20261127_client_project_hiring_intent_phase14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Project Invitations
    op.create_table(
        "project_invitations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("native_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("employer_organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("freelancer_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("decline_reason", sa.String(length=256), nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_project_invitations_project_id", "project_invitations", ["project_id"])
    op.create_index("ix_project_invitations_freelancer_id", "project_invitations", ["freelancer_id"])

    # 2. Project Applications (Mutual Interest)
    op.create_table(
        "project_applications",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("native_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("freelancer_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="submitted"),
        sa.Column("structured_pitch", sa.Text(), nullable=False),
        sa.Column("relevant_artifacts", sa.JSON(), nullable=False),
        sa.Column("proposed_rate", sa.Float(), nullable=False),
        sa.Column("proposed_rate_period", sa.String(length=32), nullable=False, server_default="fixed"),
        sa.Column("estimated_days", sa.Integer(), nullable=True),
        sa.Column("decline_reason", sa.String(length=256), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_applications_project_id", "project_applications", ["project_id"])
    op.create_index("ix_project_applications_freelancer_id", "project_applications", ["freelancer_id"])

    # 3. Project Conversations
    op.create_table(
        "project_conversations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("native_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("employer_organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("freelancer_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", sa.String(length=36), sa.ForeignKey("project_applications.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_conversations_project_id", "project_conversations", ["project_id"])
    op.create_index("ix_project_conversations_freelancer_id", "project_conversations", ["freelancer_id"])

    # 4. Project Messages
    op.create_table(
        "project_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("project_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_role", sa.String(length=32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("attachments", sa.JSON(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("flagged_as_spam", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_messages_conversation_id", "project_messages", ["conversation_id"])

    # 5. Project Offers
    op.create_table(
        "project_offers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("native_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", sa.String(length=36), sa.ForeignKey("project_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("project_conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("employer_organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("freelancer_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("creator_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("creator_role", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_review"),
        sa.Column("contract_type", sa.String(length=32), nullable=False, server_default="fixed_price"),
        sa.Column("agreed_amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="USD"),
        sa.Column("milestones", sa.JSON(), nullable=False),
        sa.Column("scope_summary", sa.Text(), nullable=False),
        sa.Column("decision_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rejection_reason", sa.String(length=256), nullable=True),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_offers_project_id", "project_offers", ["project_id"])
    op.create_index("ix_project_offers_application_id", "project_offers", ["application_id"])

    # 6. Project Offer Revisions
    op.create_table(
        "project_offer_revisions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("offer_id", sa.String(length=36), sa.ForeignKey("project_offers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_role", sa.String(length=32), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False),
        sa.Column("contract_type", sa.String(length=32), nullable=False),
        sa.Column("agreed_amount", sa.Float(), nullable=False),
        sa.Column("milestones", sa.JSON(), nullable=False),
        sa.Column("scope_summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_offer_revisions_offer_id", "project_offer_revisions", ["offer_id"])

    # 7. Project Match Scores
    op.create_table(
        "project_match_scores",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("native_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("freelancer_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("skill_score", sa.Float(), nullable=False),
        sa.Column("budget_score", sa.Float(), nullable=False),
        sa.Column("availability_score", sa.Float(), nullable=False),
        sa.Column("work_pref_score", sa.Float(), nullable=False),
        sa.Column("newcomer_boost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("breakdown_json", sa.JSON(), nullable=False),
        sa.Column("missing_information_json", sa.JSON(), nullable=False),
        sa.Column("hard_filter_passed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_match_scores_project_id", "project_match_scores", ["project_id"])
    op.create_index("ix_project_match_scores_freelancer_id", "project_match_scores", ["freelancer_id"])


def downgrade() -> None:
    op.drop_table("project_match_scores")
    op.drop_table("project_offer_revisions")
    op.drop_table("project_offers")
    op.drop_table("project_messages")
    op.drop_table("project_conversations")
    op.drop_table("project_applications")
    op.drop_table("project_invitations")
