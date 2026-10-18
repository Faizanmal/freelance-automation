"""Add commercial billing fields and per-user alert destinations.

Revision ID: 20260719b
Revises: 20260719
Create Date: 2026-07-19 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260719b"
down_revision = "20260719"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("plan", sa.String(length=32), nullable=False, server_default="free"),
    )
    op.add_column(
        "users",
        sa.Column(
            "subscription_status",
            sa.String(length=32),
            nullable=False,
            server_default="inactive",
        ),
    )
    op.add_column(
        "users", sa.Column("stripe_customer_id", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("stripe_subscription_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_users_stripe_customer_id", "users", ["stripe_customer_id"], unique=False
    )

    op.add_column(
        "user_preferences",
        sa.Column("alert_email", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "user_preferences",
        sa.Column("slack_webhook_url", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "user_preferences",
        sa.Column("telegram_chat_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "user_preferences",
        sa.Column("discord_webhook_url", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "user_preferences",
        sa.Column("whatsapp_to", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "whatsapp_to")
    op.drop_column("user_preferences", "discord_webhook_url")
    op.drop_column("user_preferences", "telegram_chat_id")
    op.drop_column("user_preferences", "slack_webhook_url")
    op.drop_column("user_preferences", "alert_email")
    op.drop_index("ix_users_stripe_customer_id", table_name="users")
    op.drop_column("users", "stripe_subscription_id")
    op.drop_column("users", "stripe_customer_id")
    op.drop_column("users", "subscription_status")
    op.drop_column("users", "plan")
