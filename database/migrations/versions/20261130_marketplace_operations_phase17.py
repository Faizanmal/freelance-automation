"""Phase 17 support queue and marketplace operations."""
import sqlalchemy as sa
from alembic import op

revision = "20261130_marketplace_operations_phase17"
down_revision = "20261129_contracts_payments_disputes_phase16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contract_disputes", sa.Column("resolution_note", sa.Text(), nullable=True))
    op.add_column("contract_disputes", sa.Column("resolved_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("contract_disputes", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("verification_claims", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_verification_claims_expires_at", "verification_claims", ["expires_at"])
    op.create_table(
        "marketplace_support_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("requester_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("assigned_to_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("resolution_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_marketplace_support_cases_requester_user_id", "marketplace_support_cases", ["requester_user_id"])
    op.create_index("ix_marketplace_support_cases_status", "marketplace_support_cases", ["status"])
    op.create_index("ix_marketplace_support_cases_created_at", "marketplace_support_cases", ["created_at"])
    op.create_table(
        "marketplace_waitlist_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("persona", sa.String(24), nullable=False),
        sa.Column("concierge_consent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(24), nullable=False, server_default="waitlisted"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "persona", name="uq_marketplace_waitlist_user_persona"),
    )
    op.create_index("ix_marketplace_waitlist_entries_user_id", "marketplace_waitlist_entries", ["user_id"])


def downgrade() -> None:
    op.drop_table("marketplace_waitlist_entries")
    op.drop_table("marketplace_support_cases")
    op.drop_index("ix_verification_claims_expires_at", table_name="verification_claims")
    op.drop_column("verification_claims", "expires_at")
    op.drop_column("contract_disputes", "resolved_at")
    op.drop_column("contract_disputes", "resolved_by_id")
    op.drop_column("contract_disputes", "resolution_note")
