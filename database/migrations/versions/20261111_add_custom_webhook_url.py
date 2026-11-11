"""Add custom_webhook_url on user_preferences.

Revision ID: 20261111_add_custom_webhook_url
Revises: 20261105b_add_github_id_to_users
Create Date: 2026-11-11 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261111_add_custom_webhook_url"
down_revision = "20261105b_add_github_id_to_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column(
            "custom_webhook_url",
            sa.String(length=1024),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "custom_webhook_url")

