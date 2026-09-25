"""Add users, preferences, and job enrichment columns

Revision ID: 20260715
Revises: 20260630
Create Date: 2026-07-15 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260715"
down_revision = "20260630"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=256), nullable=False),
        sa.Column("full_name", sa.String(length=256), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("locale", sa.String(length=16), nullable=True),
        sa.Column("hashed_password", sa.String(length=256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("exclude_keywords", sa.JSON(), nullable=False),
        sa.Column("min_budget", sa.Float(), nullable=True),
        sa.Column("max_budget", sa.Float(), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("match_threshold", sa.Float(), nullable=False, server_default="0.35"),
        sa.Column("notification_channels", sa.JSON(), nullable=False),
        sa.Column("digest_mode", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.add_column("jobs", sa.Column("location", sa.String(length=256), nullable=True))
    op.add_column("jobs", sa.Column("tags", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "tags")
    op.drop_column("jobs", "location")
    op.drop_table("user_preferences")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
