"""Privacy-minimal, consent-gated product learning events (Phase 19)."""
from alembic import op
import sqlalchemy as sa

revision = "20261201_product_learning_events_phase19"
down_revision = "20261130_marketplace_operations_phase17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_key", sa.String(36), nullable=False),
        sa.Column("event_name", sa.String(64), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("properties", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.UniqueConstraint("user_id", "event_key", name="uq_product_event_user_key"),
    )
    op.create_index("ix_product_events_user_id", "product_events", ["user_id"])
    op.create_index("ix_product_events_name_environment_time", "product_events", ["event_name", "environment", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_product_events_name_environment_time", table_name="product_events")
    op.drop_index("ix_product_events_user_id", table_name="product_events")
    op.drop_table("product_events")
