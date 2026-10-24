"""Widen jobs.source_id for long Google Jobs tokens.

Revision ID: 20261024
Revises: 20261015b
Create Date: 2026-10-24 18:40:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261024"
down_revision = "20261015b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Application also hashes oversized ids; widen for safety / older rows.
    op.alter_column(
        "jobs",
        "source_id",
        existing_type=sa.String(length=256),
        type_=sa.String(length=512),
        existing_nullable=False,
    )
    op.alter_column(
        "job_sources",
        "source_id",
        existing_type=sa.String(length=256),
        type_=sa.String(length=512),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "job_sources",
        "source_id",
        existing_type=sa.String(length=512),
        type_=sa.String(length=256),
        existing_nullable=False,
    )
    op.alter_column(
        "jobs",
        "source_id",
        existing_type=sa.String(length=512),
        type_=sa.String(length=256),
        existing_nullable=False,
    )
