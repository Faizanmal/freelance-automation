"""Add job duplicate tracking tables

Revision ID: 20260630
Revises: 
Create Date: 2026-06-30 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260630"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=256), nullable=False),
        sa.Column("canonical_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("company", sa.String(length=512), nullable=True),
        sa.Column("budget_min", sa.Float(), nullable=True),
        sa.Column("budget_max", sa.Float(), nullable=True),
        sa.Column("posted_at", sa.String(length=64), nullable=True),
        sa.Column("embedding_vector", sa.JSON(), nullable=True),
        sa.Column("duplicate_confidence", sa.Float(), nullable=True),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_name", "source_id", name="uq_jobs_source"),
        sa.UniqueConstraint("canonical_id", name="uq_jobs_canonical_id"),
    )
    op.create_index(op.f("ix_jobs_source_name"), "jobs", ["source_name"], unique=False)
    op.create_index(op.f("ix_jobs_source_id"), "jobs", ["source_id"], unique=False)
    op.create_index(op.f("ix_jobs_canonical_id"), "jobs", ["canonical_id"], unique=False)
    op.create_index(op.f("ix_jobs_url"), "jobs", ["url"], unique=False)

    op.create_table(
        "job_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=256), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_sources_job_id"), "job_sources", ["job_id"], unique=False)
    op.create_index(op.f("ix_job_sources_source_name"), "job_sources", ["source_name"], unique=False)
    op.create_index(op.f("ix_job_sources_source_id"), "job_sources", ["source_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_sources_source_id"), table_name="job_sources")
    op.drop_index(op.f("ix_job_sources_source_name"), table_name="job_sources")
    op.drop_index(op.f("ix_job_sources_job_id"), table_name="job_sources")
    op.drop_table("job_sources")
    op.drop_index(op.f("ix_jobs_url"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_canonical_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_source_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_source_name"), table_name="jobs")
    op.drop_table("jobs")
