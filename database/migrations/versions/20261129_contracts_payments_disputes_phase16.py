"""Phase 16 contract-only foundation; no payment processing."""
from alembic import op
import sqlalchemy as sa

revision = "20261129_contracts_payments_disputes_phase16"
down_revision = "20261128_fair_marketplace_matching_phase15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("project_contracts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("offer_id", sa.String(36), sa.ForeignKey("project_offers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False), sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("freelancer_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False), sa.Column("state", sa.String(32), nullable=False, server_default="awaiting_acknowledgments"),
        sa.Column("client_ack_at", sa.DateTime(timezone=True)), sa.Column("freelancer_ack_at", sa.DateTime(timezone=True)),
        sa.Column("termination_requested_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("termination_requested_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("offer_id", name="uq_project_contract_offer"))
    for table, column in (("project_contracts", "offer_id"), ("project_contracts", "project_id"), ("project_contracts", "org_id"), ("project_contracts", "freelancer_id")):
        op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_table("contract_milestones",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("contract_id", sa.String(36), sa.ForeignKey("project_contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False), sa.Column("terms", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="draft"), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_contract_milestones_contract_id", "contract_milestones", ["contract_id"])
    op.create_table("contract_events",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("contract_id", sa.String(36), sa.ForeignKey("project_contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_contract_events_contract_id", "contract_events", ["contract_id"])
    op.create_table("contract_change_orders",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("contract_id", sa.String(36), sa.ForeignKey("project_contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="awaiting_acceptance"), sa.Column("client_accepted_at", sa.DateTime(timezone=True)),
        sa.Column("freelancer_accepted_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_contract_change_orders_contract_id", "contract_change_orders", ["contract_id"])
    op.create_table("contract_disputes",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("contract_id", sa.String(36), sa.ForeignKey("project_contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("reason", sa.String(48), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False), sa.Column("evidence", sa.JSON(), nullable=False), sa.Column("state", sa.String(32), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_contract_disputes_contract_id", "contract_disputes", ["contract_id"])
    op.create_table("contract_dispute_addenda",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("dispute_id", sa.String(36), sa.ForeignKey("contract_disputes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_contract_dispute_addenda_dispute_id", "contract_dispute_addenda", ["dispute_id"])


def downgrade() -> None:
    op.drop_table("contract_dispute_addenda")
    op.drop_table("contract_disputes")
    op.drop_table("contract_change_orders")
    op.drop_table("contract_events")
    op.drop_table("contract_milestones")
    op.drop_table("project_contracts")
