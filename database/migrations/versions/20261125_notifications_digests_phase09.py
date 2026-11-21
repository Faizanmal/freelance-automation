"""Phase 09 — Reliable alerts, scheduled digests, transactional outbox, and in-app inbox.

Revision ID: 20261125_notifications_digests_phase09
Revises: 20261122_copilot_crm_workflow
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261125_notifications_digests_phase09"
down_revision = "20261122_copilot_crm_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Update user_preferences table
    op.add_column(
        "user_preferences",
        sa.Column("cadence", sa.String(length=32), nullable=False, server_default="daily"),
    )
    op.add_column(
        "user_preferences",
        sa.Column("quiet_hours_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "user_preferences",
        sa.Column("quiet_hours_start", sa.String(length=8), nullable=False, server_default="22:00"),
    )
    op.add_column(
        "user_preferences",
        sa.Column("quiet_hours_end", sa.String(length=8), nullable=False, server_default="08:00"),
    )
    op.add_column(
        "user_preferences",
        sa.Column("event_types", sa.JSON(), nullable=True),
    )
    op.add_column(
        "user_preferences",
        sa.Column("is_paused", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "user_preferences",
        sa.Column("is_unsubscribed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "user_preferences",
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "user_preferences",
        sa.Column("empty_digest_policy", sa.String(length=32), nullable=False, server_default="suppress"),
    )
    op.add_column(
        "user_preferences",
        sa.Column("immediate_alerts_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "user_preferences",
        sa.Column("immediate_alert_threshold", sa.Float(), nullable=False, server_default="0.85"),
    )
    op.add_column(
        "user_preferences",
        sa.Column("immediate_alert_cap_per_day", sa.Integer(), nullable=False, server_default="5"),
    )
    op.add_column(
        "user_preferences",
        sa.Column("immediate_alerts_sent_today", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_preferences",
        sa.Column("immediate_alerts_date", sa.String(length=10), nullable=True),
    )

    # 2. Update notifications table for in-app inbox
    op.add_column(
        "notifications",
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "notifications",
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("event_type", sa.String(length=64), nullable=False, server_default="lead_match"),
    )
    op.add_column(
        "notifications",
        sa.Column("group_key", sa.String(length=128), nullable=True),
    )
    op.create_index("ix_notifications_group_key", "notifications", ["group_key"])

    # 3. Create notification_outbox table
    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dedup_key", sa.String(length=256), nullable=False, unique=True),
        sa.Column("recipient", sa.String(length=256), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False, server_default="lead_match"),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("html_body", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_notification_outbox_dedup", "notification_outbox", ["dedup_key"])
    op.create_index("ix_notification_outbox_status", "notification_outbox", ["status"])

    # 4. Create digest_sent_jobs table
    op.create_table(
        "digest_sent_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("digest_id", sa.String(length=64), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_digest_sent_jobs_user_job", "digest_sent_jobs", ["user_id", "job_id"])


def downgrade() -> None:
    op.drop_table("digest_sent_jobs")
    op.drop_table("notification_outbox")
    op.drop_column("notifications", "group_key")
    op.drop_column("notifications", "event_type")
    op.drop_column("notifications", "archived_at")
    op.drop_column("notifications", "read_at")
    op.drop_column("notifications", "is_read")
    for col in [
        "immediate_alerts_date",
        "immediate_alerts_sent_today",
        "immediate_alert_cap_per_day",
        "immediate_alert_threshold",
        "immediate_alerts_enabled",
        "empty_digest_policy",
        "unsubscribed_at",
        "is_unsubscribed",
        "is_paused",
        "event_types",
        "quiet_hours_end",
        "quiet_hours_start",
        "quiet_hours_enabled",
        "cadence",
    ]:
        op.drop_column("user_preferences", col)
