"""Phase 08 — CRM pipeline, notes/tasks/reminders, durable agent runs, drafts.

Revision ID: 20261122_copilot_crm_workflow
Revises: 20261121_match_feedback_reasons
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261122_copilot_crm_workflow"
down_revision = "20261121_match_feedback_reasons"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend user_lead_actions with CRM fields
    op.add_column(
        "user_lead_actions",
        sa.Column("pipeline_stage", sa.String(length=32), nullable=False, server_default="saved"),
    )
    op.add_column(
        "user_lead_actions",
        sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "user_lead_actions",
        sa.Column("apply_clicked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "user_lead_actions",
        sa.Column("applied_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("user_lead_actions", sa.Column("tags", sa.JSON(), nullable=True))
    op.add_column(
        "user_lead_actions",
        sa.Column("employer_name", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "user_lead_actions",
        sa.Column("contact_name", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "user_lead_actions",
        sa.Column("contact_email", sa.String(length=320), nullable=True),
    )
    op.add_column(
        "user_lead_actions",
        sa.Column("contact_url", sa.String(length=1024), nullable=True),
    )
    op.add_column("user_lead_actions", sa.Column("contact_notes", sa.Text(), nullable=True))
    op.add_column("user_lead_actions", sa.Column("won_value", sa.Float(), nullable=True))
    op.add_column(
        "user_lead_actions",
        sa.Column("lost_reason", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "user_lead_actions",
        sa.Column("time_spent_seconds", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_lead_actions",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_lead_actions_pipeline_stage", "user_lead_actions", ["pipeline_stage"])
    op.create_index("ix_user_lead_actions_follow_up_at", "user_lead_actions", ["follow_up_at"])
    op.create_index("ix_user_lead_actions_deleted_at", "user_lead_actions", ["deleted_at"])

    # Migrate legacy status → pipeline_stage
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE user_lead_actions SET pipeline_stage = CASE status "
            "WHEN 'save' THEN 'saved' "
            "WHEN 'skip' THEN 'archived' "
            "WHEN 'pitched' THEN 'applied' "
            "WHEN 'won' THEN 'won' "
            "ELSE 'saved' END"
        )
    )

    op.create_table(
        "lead_stage_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("lead_action_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("from_stage", sa.String(length=32), nullable=True),
        sa.Column("to_stage", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=128), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_action_id"], ["user_lead_actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_stage_events_user_id", "lead_stage_events", ["user_id"])
    op.create_index("ix_lead_stage_events_lead_action_id", "lead_stage_events", ["lead_action_id"])
    op.create_index("ix_lead_stage_events_job_id", "lead_stage_events", ["job_id"])
    op.create_index("ix_lead_stage_events_created_at", "lead_stage_events", ["created_at"])

    # Seed history from migrated rows
    conn.execute(
        sa.text(
            "INSERT INTO lead_stage_events "
            "(user_id, lead_action_id, job_id, from_stage, to_stage, reason, source) "
            "SELECT user_id, id, job_id, NULL, pipeline_stage, 'migration', 'migrate' "
            "FROM user_lead_actions WHERE deleted_at IS NULL"
        )
    )

    op.create_table(
        "lead_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("lead_action_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_action_id"], ["user_lead_actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_notes_user_id", "lead_notes", ["user_id"])
    op.create_index("ix_lead_notes_lead_action_id", "lead_notes", ["lead_action_id"])
    op.create_index("ix_lead_notes_job_id", "lead_notes", ["job_id"])

    op.create_table(
        "lead_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("lead_action_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_action_id"], ["user_lead_actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_tasks_user_id", "lead_tasks", ["user_id"])
    op.create_index("ix_lead_tasks_lead_action_id", "lead_tasks", ["lead_action_id"])
    op.create_index("ix_lead_tasks_job_id", "lead_tasks", ["job_id"])

    op.create_table(
        "lead_reminders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("lead_action_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.String(length=512), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_action_id"], ["user_lead_actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "lead_action_id", "remind_at", "kind", name="uq_lead_reminder_slot"
        ),
    )
    op.create_index("ix_lead_reminders_user_id", "lead_reminders", ["user_id"])
    op.create_index("ix_lead_reminders_lead_action_id", "lead_reminders", ["lead_action_id"])
    op.create_index("ix_lead_reminders_job_id", "lead_reminders", ["job_id"])
    op.create_index("ix_lead_reminders_remind_at", "lead_reminders", ["remind_at"])

    op.create_table(
        "copilot_drafts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("lead_action_id", sa.Integer(), nullable=True),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("agent_run_id", sa.String(length=36), nullable=True),
        sa.Column("intent", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("unverified_claims", sa.JSON(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_action_id"], ["user_lead_actions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_copilot_drafts_user_id", "copilot_drafts", ["user_id"])
    op.create_index("ix_copilot_drafts_lead_action_id", "copilot_drafts", ["lead_action_id"])
    op.create_index("ix_copilot_drafts_job_id", "copilot_drafts", ["job_id"])
    op.create_index("ix_copilot_drafts_agent_run_id", "copilot_drafts", ["agent_run_id"])

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("lead_action_id", sa.Integer(), nullable=True),
        sa.Column("intent", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("input_refs", sa.JSON(), nullable=True),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("budget_tokens", sa.Integer(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("parent_run_id", sa.String(length=36), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_action_id"], ["user_lead_actions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])
    op.create_index("ix_agent_runs_job_id", "agent_runs", ["job_id"])
    op.create_index("ix_agent_runs_lead_action_id", "agent_runs", ["lead_action_id"])
    op.create_index("ix_agent_runs_intent", "agent_runs", ["intent"])
    op.create_index("ix_agent_runs_state", "agent_runs", ["state"])
    op.create_index("ix_agent_runs_idempotency_key", "agent_runs", ["idempotency_key"])
    op.create_index("ix_agent_runs_created_at", "agent_runs", ["created_at"])

    op.create_table(
        "agent_tool_calls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("args_redacted", sa.JSON(), nullable=True),
        sa.Column("result_redacted", sa.JSON(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("error", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_tool_calls_run_id", "agent_tool_calls", ["run_id"])

    op.create_table(
        "pipeline_undo_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pipeline_undo_events_user_id", "pipeline_undo_events", ["user_id"])
    op.create_index("ix_pipeline_undo_events_expires_at", "pipeline_undo_events", ["expires_at"])


def downgrade() -> None:
    op.drop_table("pipeline_undo_events")
    op.drop_table("agent_tool_calls")
    op.drop_table("agent_runs")
    op.drop_table("copilot_drafts")
    op.drop_table("lead_reminders")
    op.drop_table("lead_tasks")
    op.drop_table("lead_notes")
    op.drop_table("lead_stage_events")

    op.drop_index("ix_user_lead_actions_deleted_at", table_name="user_lead_actions")
    op.drop_index("ix_user_lead_actions_follow_up_at", table_name="user_lead_actions")
    op.drop_index("ix_user_lead_actions_pipeline_stage", table_name="user_lead_actions")
    for col in (
        "deleted_at",
        "time_spent_seconds",
        "lost_reason",
        "won_value",
        "contact_notes",
        "contact_url",
        "contact_email",
        "contact_name",
        "employer_name",
        "tags",
        "applied_confirmed_at",
        "apply_clicked_at",
        "follow_up_at",
        "pipeline_stage",
    ):
        op.drop_column("user_lead_actions", col)
