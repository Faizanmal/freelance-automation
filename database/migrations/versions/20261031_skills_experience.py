"""Add skills and experience_level on user_preferences.

Revision ID: 20261031
Revises: 20261024
Create Date: 2026-10-31 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261031"
down_revision = "20261024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column(
            "skills",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "user_preferences",
        sa.Column(
            "experience_level",
            sa.String(length=32),
            nullable=True,
            server_default="any",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "experience_level")
    op.drop_column("user_preferences", "skills")
