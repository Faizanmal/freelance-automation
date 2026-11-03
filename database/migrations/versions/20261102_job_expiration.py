"""Add is_expired, expired_at, and expired_reason to jobs.

Revision ID: 20261102_job_expiration
Revises: 20261101_min_hourly_rate
Create Date: 2026-11-02 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261102_job_expiration"
down_revision = "20261101_min_hourly_rate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "is_expired",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "expired_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "expired_reason",
            sa.String(length=128),
            nullable=True,
        ),
    )
    op.create_index("ix_jobs_is_expired", "jobs", ["is_expired"])


def downgrade() -> None:
    op.drop_index("ix_jobs_is_expired", table_name="jobs")
    op.drop_column("jobs", "expired_reason")
    op.drop_column("jobs", "expired_at")
    op.drop_column("jobs", "is_expired")
