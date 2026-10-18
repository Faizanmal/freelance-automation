"""Add user_lead_actions for Save/Skip.

Revision ID: 20261015b
Revises: 20261015
Create Date: 2026-10-15 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261015b"
down_revision = "20261015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_lead_actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "job_id", name="uq_user_lead_action"),
    )
    op.create_index("ix_user_lead_actions_user_id", "user_lead_actions", ["user_id"])
    op.create_index("ix_user_lead_actions_job_id", "user_lead_actions", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_user_lead_actions_job_id", table_name="user_lead_actions")
    op.drop_index("ix_user_lead_actions_user_id", table_name="user_lead_actions")
    op.drop_table("user_lead_actions")
