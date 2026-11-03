"""Add min_hourly_rate on user_preferences.

Revision ID: 20261101_min_hourly_rate
Revises: 20261031
Create Date: 2026-11-01 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261101_min_hourly_rate"
down_revision = "20261031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column(
            "min_hourly_rate",
            sa.Float(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "min_hourly_rate")

