"""Add verification, TOTP, roadmap votes, exit surveys, and job list indexes.

Revision ID: 20260930
Revises: 20260719b
Create Date: 2026-09-30 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260930"
down_revision = "20260719b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing accounts stay verified. New rows set is_verified in application code.
    op.add_column(
        "users",
        sa.Column(
            "is_verified", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
    )
    op.add_column(
        "users", sa.Column("totp_secret", sa.String(length=32), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column(
            "is_totp_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.create_table(
        "roadmap_votes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("feature_key", sa.String(length=64), nullable=False),
        sa.Column("voter_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feature_key", "voter_id", name="uq_roadmap_vote"),
    )
    op.create_index(
        "ix_roadmap_votes_feature_key", "roadmap_votes", ["feature_key"], unique=False
    )
    op.create_index(
        "ix_roadmap_votes_voter_id", "roadmap_votes", ["voter_id"], unique=False
    )

    op.create_table(
        "cancellation_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("email", sa.String(length=256), nullable=True),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cancellation_feedback_user_id",
        "cancellation_feedback",
        ["user_id"],
        unique=False,
    )

    op.create_index("ix_jobs_created_at", "jobs", ["created_at"], unique=False)
    op.create_index(
        "ix_jobs_source_created", "jobs", ["source_name", "created_at"], unique=False
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.create_index(
            "ix_jobs_title_trgm",
            "jobs",
            ["title"],
            unique=False,
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        )
        op.create_index(
            "ix_jobs_company_trgm",
            "jobs",
            ["company"],
            unique=False,
            postgresql_using="gin",
            postgresql_ops={"company": "gin_trgm_ops"},
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_index("ix_jobs_company_trgm", table_name="jobs")
        op.drop_index("ix_jobs_title_trgm", table_name="jobs")
    op.drop_index("ix_jobs_source_created", table_name="jobs")
    op.drop_index("ix_jobs_created_at", table_name="jobs")
    op.drop_index(
        "ix_cancellation_feedback_user_id", table_name="cancellation_feedback"
    )
    op.drop_table("cancellation_feedback")
    op.drop_index("ix_roadmap_votes_voter_id", table_name="roadmap_votes")
    op.drop_index("ix_roadmap_votes_feature_key", table_name="roadmap_votes")
    op.drop_table("roadmap_votes")
    op.drop_column("users", "is_totp_enabled")
    op.drop_column("users", "totp_secret")
    op.drop_column("users", "is_verified")
