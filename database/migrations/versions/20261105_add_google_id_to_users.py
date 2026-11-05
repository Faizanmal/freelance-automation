"""Add google_id to users.

Revision ID: 20261105_add_google_id_to_users
Revises: 20261102_job_expiration
Create Date: 2026-11-05 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261105_add_google_id_to_users"
down_revision = "20261102_job_expiration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "google_id",
            sa.String(length=128),
            nullable=True,
        ),
    )
    op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_google_id", table_name="users")
    op.drop_column("users", "google_id")

