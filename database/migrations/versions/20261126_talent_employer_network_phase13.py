"""Phase 13 — Verified talent and employer network (marketplace foundation).

Revision ID: 20261126_talent_employer_network_phase13
Revises: 20261125_notifications_digests_phase09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261126_talent_employer_network_phase13"
down_revision = "20261125_notifications_digests_phase09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Talent Profiles
    op.create_table(
        "talent_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("headline", sa.String(length=256), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("primary_segment", sa.String(length=64), nullable=False, server_default="ai_software_automation"),
        sa.Column("years_experience", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("location_display", sa.String(length=128), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_draft", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_sample", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="private"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_talent_profiles_user_id", "talent_profiles", ["user_id"])

    # 2. Talent Skills
    op.create_table(
        "talent_skills",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("profile_id", sa.String(length=36), sa.ForeignKey("talent_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_name", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="software"),
        sa.Column("years_of_experience", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("verification_status", sa.String(length=32), nullable=False, server_default="unverified"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_talent_skills_profile_id", "talent_skills", ["profile_id"])
    op.create_index("ix_talent_skills_skill_name", "talent_skills", ["skill_name"])

    # 3. Portfolio Artifacts
    op.create_table(
        "portfolio_artifacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("profile_id", sa.String(length=36), sa.ForeignKey("talent_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("artifact_type", sa.String(length=64), nullable=False, server_default="github_repo"),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("contribution_role", sa.String(length=64), nullable=False, server_default="contributor"),
        sa.Column("verification_status", sa.String(length=32), nullable=False, server_default="unverified"),
        sa.Column("evidence_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_portfolio_artifacts_profile_id", "portfolio_artifacts", ["profile_id"])

    # 4. Work Availability
    op.create_table(
        "talent_availabilities",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("profile_id", sa.String(length=36), sa.ForeignKey("talent_profiles.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="available"),
        sa.Column("hours_per_week", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("available_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_talent_availabilities_profile_id", "talent_availabilities", ["profile_id"])

    # 5. Rate Preference
    op.create_table(
        "talent_rates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("profile_id", sa.String(length=36), sa.ForeignKey("talent_profiles.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("min_rate", sa.Float(), nullable=False, server_default="50.0"),
        sa.Column("max_rate", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="USD"),
        sa.Column("rate_type", sa.String(length=32), nullable=False, server_default="hourly"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_talent_rates_profile_id", "talent_rates", ["profile_id"])

    # 6. Public Listing Consent
    op.create_table(
        "talent_listing_consents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("profile_id", sa.String(length=36), sa.ForeignKey("talent_profiles.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("opt_in_directory", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allow_platform_contact", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("search_indexing_consent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_talent_listing_consents_profile_id", "talent_listing_consents", ["profile_id"])

    # 7. Employer Organizations
    op.create_table(
        "employer_organizations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False, unique=True),
        sa.Column("website", sa.String(length=256), nullable=True),
        sa.Column("industry", sa.String(length=128), nullable=False, server_default="technology"),
        sa.Column("org_domain", sa.String(length=128), nullable=True),
        sa.Column("domain_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("verification_status", sa.String(length=32), nullable=False, server_default="unverified"),
        sa.Column("owner_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_sample", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_employer_organizations_slug", "employer_organizations", ["slug"])
    op.create_index("ix_employer_organizations_owner_id", "employer_organizations", ["owner_id"])

    # 8. Employer Memberships
    op.create_table(
        "employer_memberships",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("employer_organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("email", sa.String(length=256), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="member"),
        sa.Column("seat_status", sa.String(length=32), nullable=False, server_default="invited"),
        sa.Column("invitation_token", sa.String(length=128), nullable=True, unique=True),
        sa.Column("invited_by_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_employer_memberships_org_id", "employer_memberships", ["org_id"])
    op.create_index("ix_employer_memberships_user_id", "employer_memberships", ["user_id"])
    op.create_index("ix_employer_memberships_email", "employer_memberships", ["email"])

    # 9. Seat Audit Logs
    op.create_table(
        "employer_seat_audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("employer_organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_employer_seat_audit_logs_org_id", "employer_seat_audit_logs", ["org_id"])

    # 10. Verification Claims
    op.create_table(
        "verification_claims",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.String(length=36), sa.ForeignKey("talent_profiles.id", ondelete="CASCADE"), nullable=True),
        sa.Column("claim_type", sa.String(length=64), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("claim_source", sa.String(length=32), nullable=False, server_default="user_claimed"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_verification_claims_user_id", "verification_claims", ["user_id"])
    op.create_index("ix_verification_claims_profile_id", "verification_claims", ["profile_id"])

    # 11. Verification Evidences
    op.create_table(
        "verification_evidences",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("claim_id", sa.String(length=36), sa.ForeignKey("verification_claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("provider_reference_id", sa.String(length=256), nullable=True),
        sa.Column("evidence_payload", sa.JSON(), nullable=True),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correction_notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_verification_evidences_claim_id", "verification_evidences", ["claim_id"])

    # 12. Marketplace Reports and Appeals
    op.create_table(
        "marketplace_reports_and_appeals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("reporter_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("report_type", sa.String(length=32), nullable=False, server_default="report"),
        sa.Column("reason", sa.String(length=128), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="opened"),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolved_by_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_marketplace_reports_reporter", "marketplace_reports_and_appeals", ["reporter_user_id"])
    op.create_index("ix_marketplace_reports_target", "marketplace_reports_and_appeals", ["target_id"])

    # 13. Reputation Activities
    op.create_table(
        "reputation_activities",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("counterparty_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entity_type", sa.String(length=32), nullable=False, server_default="freelancer"),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("transaction_amount", sa.Float(), nullable=True),
        sa.Column("response_time_seconds", sa.Integer(), nullable=True),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("is_verified_event", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_suspicious", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("decay_weight", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.create_index("ix_reputation_activities_user_id", "reputation_activities", ["user_id"])


def downgrade() -> None:
    op.drop_table("reputation_activities")
    op.drop_table("marketplace_reports_and_appeals")
    op.drop_table("verification_evidences")
    op.drop_table("verification_claims")
    op.drop_table("employer_seat_audit_logs")
    op.drop_table("employer_memberships")
    op.drop_table("employer_organizations")
    op.drop_table("talent_listing_consents")
    op.drop_table("talent_rates")
    op.drop_table("talent_availabilities")
    op.drop_table("portfolio_artifacts")
    op.drop_table("talent_skills")
    op.drop_table("talent_profiles")
