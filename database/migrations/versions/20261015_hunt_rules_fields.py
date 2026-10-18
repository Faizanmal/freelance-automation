"""Add freelance_focus and show-clock fields on user_preferences.

Revision ID: 20261015
Revises: 20260930
Create Date: 2026-10-15 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261015"
down_revision = "20260930"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column(
            "freelance_focus",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "user_preferences",
        sa.Column("location", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "user_preferences",
        sa.Column("timezone", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "user_preferences",
        sa.Column("digest_days", sa.JSON(), nullable=True),
    )
    op.add_column(
        "user_preferences",
        sa.Column("digest_time_local", sa.String(length=8), nullable=True),
    )
    op.add_column(
        "user_preferences",
        sa.Column(
            "max_per_digest",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("10"),
        ),
    )
    op.add_column(
        "user_preferences",
        sa.Column("digest_last_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "digest_last_sent_at")
    op.drop_column("user_preferences", "max_per_digest")
    op.drop_column("user_preferences", "digest_time_local")
    op.drop_column("user_preferences", "digest_days")
    op.drop_column("user_preferences", "timezone")
    op.drop_column("user_preferences", "location")
    op.drop_column("user_preferences", "freelance_focus")
