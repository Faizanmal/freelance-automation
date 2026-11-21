"""Add reason + feedback_kind to user_lead_actions for Phase 07.

Revision ID: 20261121_match_feedback_reasons
Revises: 20261120_identity_privacy
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261121_match_feedback_reasons"
down_revision = "20261120_identity_privacy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_lead_actions",
        sa.Column("reason", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "user_lead_actions",
        sa.Column("feedback_kind", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_lead_actions", "feedback_kind")
    op.drop_column("user_lead_actions", "reason")
