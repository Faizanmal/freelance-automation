from __future__ import annotations

from app.core.logging.logger import get_logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

logger = get_logger(__name__)

# Column name → (sqlite DDL, postgresql DDL). Only one dialect's statement is run.
JOB_COLUMNS = {
    "is_expired": (
        "ALTER TABLE jobs ADD COLUMN is_expired BOOLEAN NOT NULL DEFAULT 0",
        "ALTER TABLE jobs ADD COLUMN is_expired BOOLEAN NOT NULL DEFAULT false",
    ),
    "expired_at": (
        "ALTER TABLE jobs ADD COLUMN expired_at DATETIME",
        "ALTER TABLE jobs ADD COLUMN expired_at TIMESTAMPTZ",
    ),
    "expired_reason": (
        "ALTER TABLE jobs ADD COLUMN expired_reason VARCHAR(128)",
        "ALTER TABLE jobs ADD COLUMN expired_reason VARCHAR(128)",
    ),
    "location": (
        "ALTER TABLE jobs ADD COLUMN location VARCHAR(256)",
        "ALTER TABLE jobs ADD COLUMN location VARCHAR(256)",
    ),
    "tags": (
        "ALTER TABLE jobs ADD COLUMN tags JSON",
        "ALTER TABLE jobs ADD COLUMN tags JSON",
    ),
    "seniority": (
        "ALTER TABLE jobs ADD COLUMN seniority VARCHAR(64)",
        "ALTER TABLE jobs ADD COLUMN seniority VARCHAR(64)",
    ),
    "analysis_summary": (
        "ALTER TABLE jobs ADD COLUMN analysis_summary TEXT",
        "ALTER TABLE jobs ADD COLUMN analysis_summary TEXT",
    ),
    "enrichment": (
        "ALTER TABLE jobs ADD COLUMN enrichment JSON",
        "ALTER TABLE jobs ADD COLUMN enrichment JSON",
    ),
    "work_type": (
        "ALTER TABLE jobs ADD COLUMN work_type VARCHAR(32)",
        "ALTER TABLE jobs ADD COLUMN work_type VARCHAR(32)",
    ),
    "compensation_period": (
        "ALTER TABLE jobs ADD COLUMN compensation_period VARCHAR(32)",
        "ALTER TABLE jobs ADD COLUMN compensation_period VARCHAR(32)",
    ),
    "compensation_currency": (
        "ALTER TABLE jobs ADD COLUMN compensation_currency VARCHAR(16)",
        "ALTER TABLE jobs ADD COLUMN compensation_currency VARCHAR(16)",
    ),
    "first_seen_at": (
        "ALTER TABLE jobs ADD COLUMN first_seen_at DATETIME",
        "ALTER TABLE jobs ADD COLUMN first_seen_at TIMESTAMPTZ",
    ),
    "last_seen_at": (
        "ALTER TABLE jobs ADD COLUMN last_seen_at DATETIME",
        "ALTER TABLE jobs ADD COLUMN last_seen_at TIMESTAMPTZ",
    ),
    "last_checked_at": (
        "ALTER TABLE jobs ADD COLUMN last_checked_at DATETIME",
        "ALTER TABLE jobs ADD COLUMN last_checked_at TIMESTAMPTZ",
    ),
    "inventory_state": (
        "ALTER TABLE jobs ADD COLUMN inventory_state VARCHAR(32) DEFAULT 'active'",
        "ALTER TABLE jobs ADD COLUMN inventory_state VARCHAR(32) DEFAULT 'active'",
    ),
}

USER_COLUMNS = {
    "plan": (
        "ALTER TABLE users ADD COLUMN plan VARCHAR(32) DEFAULT 'free'",
        "ALTER TABLE users ADD COLUMN plan VARCHAR(32) DEFAULT 'free'",
    ),
    "subscription_status": (
        "ALTER TABLE users ADD COLUMN subscription_status VARCHAR(32) DEFAULT 'inactive'",
        "ALTER TABLE users ADD COLUMN subscription_status VARCHAR(32) DEFAULT 'inactive'",
    ),
    "stripe_customer_id": (
        "ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR(128)",
        "ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR(128)",
    ),
    "stripe_subscription_id": (
        "ALTER TABLE users ADD COLUMN stripe_subscription_id VARCHAR(128)",
        "ALTER TABLE users ADD COLUMN stripe_subscription_id VARCHAR(128)",
    ),
    "is_verified": (
        "ALTER TABLE users ADD COLUMN is_verified BOOLEAN NOT NULL DEFAULT 1",
        "ALTER TABLE users ADD COLUMN is_verified BOOLEAN NOT NULL DEFAULT true",
    ),
    "totp_secret": (
        "ALTER TABLE users ADD COLUMN totp_secret VARCHAR(32)",
        "ALTER TABLE users ADD COLUMN totp_secret VARCHAR(32)",
    ),
    "is_totp_enabled": (
        "ALTER TABLE users ADD COLUMN is_totp_enabled BOOLEAN NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN is_totp_enabled BOOLEAN NOT NULL DEFAULT false",
    ),
    "account_role": (
        "ALTER TABLE users ADD COLUMN account_role VARCHAR(32) NOT NULL DEFAULT 'freelancer'",
        "ALTER TABLE users ADD COLUMN account_role VARCHAR(32) NOT NULL DEFAULT 'freelancer'",
    ),
    "profile_visibility": (
        "ALTER TABLE users ADD COLUMN profile_visibility VARCHAR(32) NOT NULL DEFAULT 'private'",
        "ALTER TABLE users ADD COLUMN profile_visibility VARCHAR(32) NOT NULL DEFAULT 'private'",
    ),
}

PREFERENCE_COLUMNS = {
    "alert_email": (
        "ALTER TABLE user_preferences ADD COLUMN alert_email VARCHAR(256)",
        "ALTER TABLE user_preferences ADD COLUMN alert_email VARCHAR(256)",
    ),
    "slack_webhook_url": (
        "ALTER TABLE user_preferences ADD COLUMN slack_webhook_url VARCHAR(1024)",
        "ALTER TABLE user_preferences ADD COLUMN slack_webhook_url VARCHAR(1024)",
    ),
    "telegram_chat_id": (
        "ALTER TABLE user_preferences ADD COLUMN telegram_chat_id VARCHAR(128)",
        "ALTER TABLE user_preferences ADD COLUMN telegram_chat_id VARCHAR(128)",
    ),
    "discord_webhook_url": (
        "ALTER TABLE user_preferences ADD COLUMN discord_webhook_url VARCHAR(1024)",
        "ALTER TABLE user_preferences ADD COLUMN discord_webhook_url VARCHAR(1024)",
    ),
    "whatsapp_to": (
        "ALTER TABLE user_preferences ADD COLUMN whatsapp_to VARCHAR(64)",
        "ALTER TABLE user_preferences ADD COLUMN whatsapp_to VARCHAR(64)",
    ),
    "freelance_focus": (
        "ALTER TABLE user_preferences ADD COLUMN freelance_focus BOOLEAN NOT NULL DEFAULT 1",
        "ALTER TABLE user_preferences ADD COLUMN freelance_focus BOOLEAN NOT NULL DEFAULT true",
    ),
    "hide_agency_leads": (
        "ALTER TABLE user_preferences ADD COLUMN hide_agency_leads BOOLEAN NOT NULL DEFAULT 0",
        "ALTER TABLE user_preferences ADD COLUMN hide_agency_leads BOOLEAN NOT NULL DEFAULT false",
    ),
    "location": (
        "ALTER TABLE user_preferences ADD COLUMN location VARCHAR(128)",
        "ALTER TABLE user_preferences ADD COLUMN location VARCHAR(128)",
    ),
    "timezone": (
        "ALTER TABLE user_preferences ADD COLUMN timezone VARCHAR(64)",
        "ALTER TABLE user_preferences ADD COLUMN timezone VARCHAR(64)",
    ),
    "digest_days": (
        "ALTER TABLE user_preferences ADD COLUMN digest_days JSON",
        "ALTER TABLE user_preferences ADD COLUMN digest_days JSON",
    ),
    "digest_time_local": (
        "ALTER TABLE user_preferences ADD COLUMN digest_time_local VARCHAR(8)",
        "ALTER TABLE user_preferences ADD COLUMN digest_time_local VARCHAR(8)",
    ),
    "max_per_digest": (
        "ALTER TABLE user_preferences ADD COLUMN max_per_digest INTEGER NOT NULL DEFAULT 10",
        "ALTER TABLE user_preferences ADD COLUMN max_per_digest INTEGER NOT NULL DEFAULT 10",
    ),
    "digest_last_sent_at": (
        "ALTER TABLE user_preferences ADD COLUMN digest_last_sent_at DATETIME",
        "ALTER TABLE user_preferences ADD COLUMN digest_last_sent_at TIMESTAMPTZ",
    ),
    "skills": (
        "ALTER TABLE user_preferences ADD COLUMN skills JSON",
        "ALTER TABLE user_preferences ADD COLUMN skills JSON",
    ),
    "experience_level": (
        "ALTER TABLE user_preferences ADD COLUMN experience_level VARCHAR(32) DEFAULT 'any'",
        "ALTER TABLE user_preferences ADD COLUMN experience_level VARCHAR(32) DEFAULT 'any'",
    ),
    "min_hourly_rate": (
        "ALTER TABLE user_preferences ADD COLUMN min_hourly_rate FLOAT",
        "ALTER TABLE user_preferences ADD COLUMN min_hourly_rate FLOAT",
    ),
    "custom_webhook_url": (
        "ALTER TABLE user_preferences ADD COLUMN custom_webhook_url VARCHAR(1024)",
        "ALTER TABLE user_preferences ADD COLUMN custom_webhook_url VARCHAR(1024)",
    ),
    "cadence": (
        "ALTER TABLE user_preferences ADD COLUMN cadence VARCHAR(32) DEFAULT 'daily'",
        "ALTER TABLE user_preferences ADD COLUMN cadence VARCHAR(32) DEFAULT 'daily'",
    ),
    "quiet_hours_enabled": (
        "ALTER TABLE user_preferences ADD COLUMN quiet_hours_enabled BOOLEAN NOT NULL DEFAULT 0",
        "ALTER TABLE user_preferences ADD COLUMN quiet_hours_enabled BOOLEAN NOT NULL DEFAULT false",
    ),
    "quiet_hours_start": (
        "ALTER TABLE user_preferences ADD COLUMN quiet_hours_start VARCHAR(8) DEFAULT '22:00'",
        "ALTER TABLE user_preferences ADD COLUMN quiet_hours_start VARCHAR(8) DEFAULT '22:00'",
    ),
    "quiet_hours_end": (
        "ALTER TABLE user_preferences ADD COLUMN quiet_hours_end VARCHAR(8) DEFAULT '08:00'",
        "ALTER TABLE user_preferences ADD COLUMN quiet_hours_end VARCHAR(8) DEFAULT '08:00'",
    ),
    "event_types": (
        "ALTER TABLE user_preferences ADD COLUMN event_types JSON",
        "ALTER TABLE user_preferences ADD COLUMN event_types JSON",
    ),
    "is_paused": (
        "ALTER TABLE user_preferences ADD COLUMN is_paused BOOLEAN NOT NULL DEFAULT 0",
        "ALTER TABLE user_preferences ADD COLUMN is_paused BOOLEAN NOT NULL DEFAULT false",
    ),
    "is_unsubscribed": (
        "ALTER TABLE user_preferences ADD COLUMN is_unsubscribed BOOLEAN NOT NULL DEFAULT 0",
        "ALTER TABLE user_preferences ADD COLUMN is_unsubscribed BOOLEAN NOT NULL DEFAULT false",
    ),
    "unsubscribed_at": (
        "ALTER TABLE user_preferences ADD COLUMN unsubscribed_at DATETIME",
        "ALTER TABLE user_preferences ADD COLUMN unsubscribed_at TIMESTAMPTZ",
    ),
    "empty_digest_policy": (
        "ALTER TABLE user_preferences ADD COLUMN empty_digest_policy VARCHAR(32) DEFAULT 'suppress'",
        "ALTER TABLE user_preferences ADD COLUMN empty_digest_policy VARCHAR(32) DEFAULT 'suppress'",
    ),
    "immediate_alerts_enabled": (
        "ALTER TABLE user_preferences ADD COLUMN immediate_alerts_enabled BOOLEAN NOT NULL DEFAULT 1",
        "ALTER TABLE user_preferences ADD COLUMN immediate_alerts_enabled BOOLEAN NOT NULL DEFAULT true",
    ),
    "immediate_alert_threshold": (
        "ALTER TABLE user_preferences ADD COLUMN immediate_alert_threshold FLOAT DEFAULT 0.85",
        "ALTER TABLE user_preferences ADD COLUMN immediate_alert_threshold FLOAT DEFAULT 0.85",
    ),
    "immediate_alert_cap_per_day": (
        "ALTER TABLE user_preferences ADD COLUMN immediate_alert_cap_per_day INTEGER NOT NULL DEFAULT 5",
        "ALTER TABLE user_preferences ADD COLUMN immediate_alert_cap_per_day INTEGER NOT NULL DEFAULT 5",
    ),
    "immediate_alerts_sent_today": (
        "ALTER TABLE user_preferences ADD COLUMN immediate_alerts_sent_today INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE user_preferences ADD COLUMN immediate_alerts_sent_today INTEGER NOT NULL DEFAULT 0",
    ),
    "immediate_alerts_date": (
        "ALTER TABLE user_preferences ADD COLUMN immediate_alerts_date VARCHAR(10)",
        "ALTER TABLE user_preferences ADD COLUMN immediate_alerts_date VARCHAR(10)",
    ),
}

NOTIFICATION_COLUMNS = {
    "is_read": (
        "ALTER TABLE notifications ADD COLUMN is_read BOOLEAN NOT NULL DEFAULT 0",
        "ALTER TABLE notifications ADD COLUMN is_read BOOLEAN NOT NULL DEFAULT false",
    ),
    "read_at": (
        "ALTER TABLE notifications ADD COLUMN read_at DATETIME",
        "ALTER TABLE notifications ADD COLUMN read_at TIMESTAMPTZ",
    ),
    "archived_at": (
        "ALTER TABLE notifications ADD COLUMN archived_at DATETIME",
        "ALTER TABLE notifications ADD COLUMN archived_at TIMESTAMPTZ",
    ),
    "event_type": (
        "ALTER TABLE notifications ADD COLUMN event_type VARCHAR(64) DEFAULT 'lead_match'",
        "ALTER TABLE notifications ADD COLUMN event_type VARCHAR(64) DEFAULT 'lead_match'",
    ),
    "group_key": (
        "ALTER TABLE notifications ADD COLUMN group_key VARCHAR(128)",
        "ALTER TABLE notifications ADD COLUMN group_key VARCHAR(128)",
    ),
}

LEAD_ACTION_COLUMNS = {
    "reason": (
        "ALTER TABLE user_lead_actions ADD COLUMN reason VARCHAR(64)",
        "ALTER TABLE user_lead_actions ADD COLUMN reason VARCHAR(64)",
    ),
    "feedback_kind": (
        "ALTER TABLE user_lead_actions ADD COLUMN feedback_kind VARCHAR(32)",
        "ALTER TABLE user_lead_actions ADD COLUMN feedback_kind VARCHAR(32)",
    ),
    "pipeline_stage": (
        "ALTER TABLE user_lead_actions ADD COLUMN pipeline_stage VARCHAR(32) NOT NULL DEFAULT 'saved'",
        "ALTER TABLE user_lead_actions ADD COLUMN pipeline_stage VARCHAR(32) NOT NULL DEFAULT 'saved'",
    ),
    "follow_up_at": (
        "ALTER TABLE user_lead_actions ADD COLUMN follow_up_at DATETIME",
        "ALTER TABLE user_lead_actions ADD COLUMN follow_up_at TIMESTAMPTZ",
    ),
    "apply_clicked_at": (
        "ALTER TABLE user_lead_actions ADD COLUMN apply_clicked_at DATETIME",
        "ALTER TABLE user_lead_actions ADD COLUMN apply_clicked_at TIMESTAMPTZ",
    ),
    "applied_confirmed_at": (
        "ALTER TABLE user_lead_actions ADD COLUMN applied_confirmed_at DATETIME",
        "ALTER TABLE user_lead_actions ADD COLUMN applied_confirmed_at TIMESTAMPTZ",
    ),
    "tags": (
        "ALTER TABLE user_lead_actions ADD COLUMN tags JSON",
        "ALTER TABLE user_lead_actions ADD COLUMN tags JSON",
    ),
    "employer_name": (
        "ALTER TABLE user_lead_actions ADD COLUMN employer_name VARCHAR(256)",
        "ALTER TABLE user_lead_actions ADD COLUMN employer_name VARCHAR(256)",
    ),
    "contact_name": (
        "ALTER TABLE user_lead_actions ADD COLUMN contact_name VARCHAR(256)",
        "ALTER TABLE user_lead_actions ADD COLUMN contact_name VARCHAR(256)",
    ),
    "contact_email": (
        "ALTER TABLE user_lead_actions ADD COLUMN contact_email VARCHAR(320)",
        "ALTER TABLE user_lead_actions ADD COLUMN contact_email VARCHAR(320)",
    ),
    "contact_url": (
        "ALTER TABLE user_lead_actions ADD COLUMN contact_url VARCHAR(1024)",
        "ALTER TABLE user_lead_actions ADD COLUMN contact_url VARCHAR(1024)",
    ),
    "contact_notes": (
        "ALTER TABLE user_lead_actions ADD COLUMN contact_notes TEXT",
        "ALTER TABLE user_lead_actions ADD COLUMN contact_notes TEXT",
    ),
    "won_value": (
        "ALTER TABLE user_lead_actions ADD COLUMN won_value FLOAT",
        "ALTER TABLE user_lead_actions ADD COLUMN won_value FLOAT",
    ),
    "lost_reason": (
        "ALTER TABLE user_lead_actions ADD COLUMN lost_reason VARCHAR(256)",
        "ALTER TABLE user_lead_actions ADD COLUMN lost_reason VARCHAR(256)",
    ),
    "time_spent_seconds": (
        "ALTER TABLE user_lead_actions ADD COLUMN time_spent_seconds INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE user_lead_actions ADD COLUMN time_spent_seconds INTEGER NOT NULL DEFAULT 0",
    ),
    "deleted_at": (
        "ALTER TABLE user_lead_actions ADD COLUMN deleted_at DATETIME",
        "ALTER TABLE user_lead_actions ADD COLUMN deleted_at TIMESTAMPTZ",
    ),
}


async def ensure_sqlite_columns(engine: AsyncEngine) -> None:
    """Back-compat alias — patches missing columns for SQLite and PostgreSQL."""
    await ensure_missing_columns(engine)


async def ensure_missing_columns(engine: AsyncEngine) -> None:
    """Best-effort ALTER for DBs created before new columns existed.

    ``create_all`` only creates missing tables; it does not add columns to
    existing ones. Local uvicorn (without Alembic) relies on this patch.
    """
    dialect = engine.url.get_backend_name()
    if dialect not in {"sqlite", "postgresql"}:
        return
    async with engine.begin() as conn:
        await _ensure_table_columns(conn, "jobs", JOB_COLUMNS, dialect)
        await _ensure_table_columns(conn, "users", USER_COLUMNS, dialect)
        await _ensure_table_columns(
            conn, "user_preferences", PREFERENCE_COLUMNS, dialect
        )
        await _ensure_table_columns(
            conn, "user_lead_actions", LEAD_ACTION_COLUMNS, dialect
        )
        await _ensure_table_columns(
            conn, "notifications", NOTIFICATION_COLUMNS, dialect
        )
        if dialect == "sqlite":
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS notification_outbox (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        dedup_key VARCHAR(256) NOT NULL UNIQUE,
                        recipient VARCHAR(256) NOT NULL,
                        user_id VARCHAR(64),
                        channel VARCHAR(32) NOT NULL,
                        event_type VARCHAR(64) NOT NULL DEFAULT 'lead_match',
                        title VARCHAR(512) NOT NULL,
                        body TEXT NOT NULL,
                        html_body TEXT,
                        payload_json JSON,
                        status VARCHAR(32) NOT NULL DEFAULT 'pending',
                        attempts INTEGER NOT NULL DEFAULT 0,
                        max_retries INTEGER NOT NULL DEFAULT 3,
                        last_error TEXT,
                        cost_usd FLOAT NOT NULL DEFAULT 0.0,
                        scheduled_for DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        last_attempt_at DATETIME,
                        delivered_at DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS digest_sent_jobs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id VARCHAR(64) NOT NULL,
                        job_id INTEGER NOT NULL,
                        digest_id VARCHAR(64),
                        sent_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_outbox_dedup ON notification_outbox (dedup_key)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_outbox_status ON notification_outbox (status)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_sent_jobs_user_job ON digest_sent_jobs (user_id, job_id)"
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS fee_templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        slug VARCHAR(64) NOT NULL UNIQUE,
                        platform VARCHAR(64) NOT NULL,
                        name VARCHAR(128) NOT NULL,
                        region VARCHAR(32) NOT NULL DEFAULT 'global',
                        contract_service_fee_pct FLOAT NOT NULL DEFAULT 0.0,
                        contract_service_fee_fixed FLOAT NOT NULL DEFAULT 0.0,
                        tax_on_fee_pct FLOAT NOT NULL DEFAULT 0.0,
                        withholding_tax_pct FLOAT NOT NULL DEFAULT 0.0,
                        withholding_base VARCHAR(16) NOT NULL DEFAULT 'gross',
                        withdrawal_fee FLOAT NOT NULL DEFAULT 0.0,
                        withdrawal_currency VARCHAR(8) NOT NULL DEFAULT 'USD',
                        processor_charge_pct FLOAT NOT NULL DEFAULT 0.0,
                        processor_charge_fixed FLOAT NOT NULL DEFAULT 0.0,
                        source_url VARCHAR(1024) NOT NULL,
                        effective_date VARCHAR(32) NOT NULL,
                        eligibility_notes TEXT NOT NULL,
                        is_system_template BOOLEAN NOT NULL DEFAULT 1,
                        user_id VARCHAR(64),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS fx_rate_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        base_currency VARCHAR(8) NOT NULL,
                        quote_currency VARCHAR(8) NOT NULL,
                        benchmark_rate FLOAT NOT NULL,
                        offered_rate FLOAT NOT NULL,
                        rate_type VARCHAR(32) NOT NULL DEFAULT 'estimated_platform',
                        provider_name VARCHAR(64) NOT NULL DEFAULT 'open_er_or_manual',
                        is_outage BOOLEAN NOT NULL DEFAULT 0,
                        rate_timestamp DATETIME NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS user_earnings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id VARCHAR(36) NOT NULL,
                        project_title VARCHAR(256) NOT NULL,
                        client_name VARCHAR(256),
                        platform VARCHAR(64) NOT NULL DEFAULT 'direct',
                        job_id INTEGER,
                        invoice_status VARCHAR(32) NOT NULL DEFAULT 'invoiced',
                        gross_amount FLOAT NOT NULL,
                        currency VARCHAR(8) NOT NULL DEFAULT 'USD',
                        platform_fee_paid FLOAT NOT NULL DEFAULT 0.0,
                        tax_on_fee_paid FLOAT NOT NULL DEFAULT 0.0,
                        withholding_paid FLOAT NOT NULL DEFAULT 0.0,
                        withdrawal_fee_paid FLOAT NOT NULL DEFAULT 0.0,
                        processor_fee_paid FLOAT NOT NULL DEFAULT 0.0,
                        net_received_usd FLOAT NOT NULL,
                        net_received_local FLOAT,
                        target_currency VARCHAR(8),
                        actual_fx_rate FLOAT,
                        hours_logged FLOAT,
                        effective_hourly_rate FLOAT,
                        invoice_date VARCHAR(10),
                        paid_at DATETIME,
                        notes TEXT,
                        metadata_json JSON,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_user_earnings_user ON user_earnings (user_id)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_user_earnings_status ON user_earnings (invoice_status)"
                )
            )
            # Phase 11 Billing & Quota tables
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS billing_webhook_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id VARCHAR(128) NOT NULL UNIQUE,
                        provider VARCHAR(32) NOT NULL DEFAULT 'stripe',
                        event_type VARCHAR(64) NOT NULL,
                        status VARCHAR(32) NOT NULL DEFAULT 'processed',
                        payload_hash VARCHAR(64),
                        event_timestamp DATETIME NOT NULL,
                        processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        error_message TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS quota_reservations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        reservation_token VARCHAR(64) NOT NULL UNIQUE,
                        user_id VARCHAR(64) NOT NULL,
                        workspace_id VARCHAR(64),
                        feature VARCHAR(64) NOT NULL,
                        units_reserved INTEGER NOT NULL DEFAULT 1,
                        units_committed INTEGER NOT NULL DEFAULT 0,
                        status VARCHAR(32) NOT NULL DEFAULT 'reserved',
                        idempotency_key VARCHAR(128),
                        expires_at DATETIME NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_quota_res_user ON quota_reservations (user_id)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_quota_res_status ON quota_reservations (status)"
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS user_usage_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id VARCHAR(64) NOT NULL,
                        feature VARCHAR(64) NOT NULL,
                        period_key VARCHAR(32) NOT NULL,
                        units_used INTEGER NOT NULL DEFAULT 0,
                        cost_estimate_usd FLOAT NOT NULL DEFAULT 0.0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_usage_user_feat ON user_usage_records (user_id, feature, period_key)"
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS subscription_lifecycle (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id VARCHAR(64) NOT NULL UNIQUE,
                        provider VARCHAR(32) NOT NULL DEFAULT 'stripe',
                        customer_id VARCHAR(128),
                        subscription_id VARCHAR(128),
                        plan VARCHAR(32) NOT NULL DEFAULT 'free',
                        status VARCHAR(32) NOT NULL DEFAULT 'inactive',
                        cancel_at_period_end BOOLEAN NOT NULL DEFAULT 0,
                        current_period_start DATETIME,
                        current_period_end DATETIME,
                        grace_period_until DATETIME,
                        last_event_timestamp DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
        if dialect == "sqlite":
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS talent_profiles (
                        id VARCHAR(36) PRIMARY KEY,
                        user_id VARCHAR(36) NOT NULL UNIQUE,
                        headline VARCHAR(256) NOT NULL,
                        bio TEXT,
                        primary_segment VARCHAR(64) NOT NULL DEFAULT 'ai_software_automation',
                        years_experience FLOAT NOT NULL DEFAULT 1.0,
                        location_display VARCHAR(128),
                        is_published BOOLEAN NOT NULL DEFAULT 0,
                        is_draft BOOLEAN NOT NULL DEFAULT 1,
                        is_sample BOOLEAN NOT NULL DEFAULT 0,
                        status VARCHAR(32) NOT NULL DEFAULT 'private',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS talent_skills (
                        id VARCHAR(36) PRIMARY KEY,
                        profile_id VARCHAR(36) NOT NULL,
                        skill_name VARCHAR(128) NOT NULL,
                        category VARCHAR(64) NOT NULL DEFAULT 'software',
                        years_of_experience FLOAT NOT NULL DEFAULT 1.0,
                        verification_status VARCHAR(32) NOT NULL DEFAULT 'unverified',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS portfolio_artifacts (
                        id VARCHAR(36) PRIMARY KEY,
                        profile_id VARCHAR(36) NOT NULL,
                        title VARCHAR(256) NOT NULL,
                        description TEXT,
                        artifact_type VARCHAR(64) NOT NULL DEFAULT 'github_repo',
                        url VARCHAR(512) NOT NULL,
                        contribution_role VARCHAR(64) NOT NULL DEFAULT 'contributor',
                        verification_status VARCHAR(32) NOT NULL DEFAULT 'unverified',
                        evidence_summary TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS talent_availabilities (
                        id VARCHAR(36) PRIMARY KEY,
                        profile_id VARCHAR(36) NOT NULL UNIQUE,
                        status VARCHAR(32) NOT NULL DEFAULT 'available',
                        hours_per_week INTEGER NOT NULL DEFAULT 40,
                        available_from DATETIME,
                        expires_at DATETIME NOT NULL,
                        last_confirmed_at DATETIME,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS talent_rates (
                        id VARCHAR(36) PRIMARY KEY,
                        profile_id VARCHAR(36) NOT NULL UNIQUE,
                        min_rate FLOAT NOT NULL DEFAULT 50.0,
                        max_rate FLOAT,
                        currency VARCHAR(8) NOT NULL DEFAULT 'USD',
                        rate_type VARCHAR(32) NOT NULL DEFAULT 'hourly',
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS talent_listing_consents (
                        id VARCHAR(36) PRIMARY KEY,
                        profile_id VARCHAR(36) NOT NULL UNIQUE,
                        opt_in_directory BOOLEAN NOT NULL DEFAULT 0,
                        allow_platform_contact BOOLEAN NOT NULL DEFAULT 0,
                        search_indexing_consent BOOLEAN NOT NULL DEFAULT 0,
                        consented_at DATETIME,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS employer_organizations (
                        id VARCHAR(36) PRIMARY KEY,
                        name VARCHAR(256) NOT NULL,
                        slug VARCHAR(128) NOT NULL UNIQUE,
                        website VARCHAR(256),
                        industry VARCHAR(128) NOT NULL DEFAULT 'technology',
                        org_domain VARCHAR(128),
                        domain_verified BOOLEAN NOT NULL DEFAULT 0,
                        verification_status VARCHAR(32) NOT NULL DEFAULT 'unverified',
                        owner_id VARCHAR(36) NOT NULL,
                        is_sample BOOLEAN NOT NULL DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS employer_memberships (
                        id VARCHAR(36) PRIMARY KEY,
                        org_id VARCHAR(36) NOT NULL,
                        user_id VARCHAR(36),
                        email VARCHAR(256) NOT NULL,
                        role VARCHAR(32) NOT NULL DEFAULT 'member',
                        seat_status VARCHAR(32) NOT NULL DEFAULT 'invited',
                        invitation_token VARCHAR(128) UNIQUE,
                        invited_by_id VARCHAR(36),
                        invited_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        accepted_at DATETIME,
                        revoked_at DATETIME,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS employer_seat_audit_logs (
                        id VARCHAR(36) PRIMARY KEY,
                        org_id VARCHAR(36) NOT NULL,
                        actor_id VARCHAR(36),
                        target_user_id VARCHAR(36),
                        action VARCHAR(64) NOT NULL,
                        ip_address VARCHAR(64),
                        user_agent VARCHAR(256),
                        details JSON,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS verification_claims (
                        id VARCHAR(36) PRIMARY KEY,
                        user_id VARCHAR(36) NOT NULL,
                        profile_id VARCHAR(36),
                        claim_type VARCHAR(64) NOT NULL,
                        level INTEGER NOT NULL DEFAULT 1,
                        claim_source VARCHAR(32) NOT NULL DEFAULT 'user_claimed',
                        status VARCHAR(32) NOT NULL DEFAULT 'pending',
                        reviewer_notes TEXT,
                        verified_at DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS verification_evidences (
                        id VARCHAR(36) PRIMARY KEY,
                        claim_id VARCHAR(36) NOT NULL,
                        provider VARCHAR(64) NOT NULL,
                        evidence_type VARCHAR(64) NOT NULL,
                        provider_reference_id VARCHAR(256),
                        evidence_payload JSON,
                        is_valid BOOLEAN NOT NULL DEFAULT 1,
                        submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        corrected_at DATETIME,
                        correction_notes TEXT
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS marketplace_reports_and_appeals (
                        id VARCHAR(36) PRIMARY KEY,
                        reporter_user_id VARCHAR(36) NOT NULL,
                        target_type VARCHAR(32) NOT NULL,
                        target_id VARCHAR(36) NOT NULL,
                        report_type VARCHAR(32) NOT NULL DEFAULT 'report',
                        reason VARCHAR(128) NOT NULL,
                        details TEXT NOT NULL,
                        status VARCHAR(32) NOT NULL DEFAULT 'opened',
                        resolution_notes TEXT,
                        resolved_by_id VARCHAR(36),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS reputation_activities (
                        id VARCHAR(36) PRIMARY KEY,
                        user_id VARCHAR(36) NOT NULL,
                        counterparty_id VARCHAR(36),
                        entity_type VARCHAR(32) NOT NULL DEFAULT 'freelancer',
                        event_type VARCHAR(64) NOT NULL,
                        transaction_amount FLOAT,
                        response_time_seconds INTEGER,
                        event_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        is_verified_event BOOLEAN NOT NULL DEFAULT 1,
                        is_suspicious BOOLEAN NOT NULL DEFAULT 0,
                        decay_weight FLOAT NOT NULL DEFAULT 1.0
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS native_projects (
                        id VARCHAR(36) PRIMARY KEY,
                        org_id VARCHAR(36) NOT NULL,
                        creator_id VARCHAR(36) NOT NULL,
                        title VARCHAR(256) NOT NULL,
                        raw_description TEXT NOT NULL,
                        ai_scope_summary TEXT,
                        ai_clarification_approved BOOLEAN NOT NULL DEFAULT 0,
                        primary_segment VARCHAR(64) NOT NULL DEFAULT 'ai_software_automation',
                        scope_level VARCHAR(32) NOT NULL DEFAULT 'medium',
                        work_type VARCHAR(32) NOT NULL DEFAULT 'remote',
                        commitment_type VARCHAR(32) NOT NULL DEFAULT 'contract',
                        required_hours_per_week INTEGER NOT NULL DEFAULT 20,
                        skills_required JSON NOT NULL,
                        acceptance_criteria JSON NOT NULL,
                        milestone_outline JSON NOT NULL,
                        budget_min FLOAT NOT NULL,
                        budget_max FLOAT NOT NULL,
                        currency VARCHAR(8) NOT NULL DEFAULT 'USD',
                        rate_period VARCHAR(32) NOT NULL DEFAULT 'fixed',
                        budget_basis_notes TEXT,
                        hiring_deadline DATETIME NOT NULL,
                        reconfirm_by DATETIME NOT NULL,
                        last_reconfirmed_at DATETIME,
                        payment_verified BOOLEAN NOT NULL DEFAULT 0,
                        payment_provider_ref VARCHAR(128),
                        status VARCHAR(32) NOT NULL DEFAULT 'draft',
                        review_state VARCHAR(32) NOT NULL DEFAULT 'draft',
                        flagged_reason VARCHAR(256),
                        abandonment_reason VARCHAR(256),
                        duplicate_hash VARCHAR(64),
                        is_sample BOOLEAN NOT NULL DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS project_status_histories (
                        id VARCHAR(36) PRIMARY KEY,
                        project_id VARCHAR(36) NOT NULL,
                        from_status VARCHAR(32),
                        to_status VARCHAR(32) NOT NULL,
                        action VARCHAR(64) NOT NULL,
                        actor_id VARCHAR(36),
                        reason VARCHAR(256),
                        metadata_json JSON,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS project_clarification_requests (
                        id VARCHAR(36) PRIMARY KEY,
                        project_id VARCHAR(36) NOT NULL,
                        freelancer_id VARCHAR(36) NOT NULL,
                        question TEXT NOT NULL,
                        answer TEXT,
                        status VARCHAR(32) NOT NULL DEFAULT 'pending',
                        is_public BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        answered_at DATETIME
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS project_candidate_shortlists (
                        id VARCHAR(36) PRIMARY KEY,
                        project_id VARCHAR(36) NOT NULL,
                        candidate_id VARCHAR(36) NOT NULL,
                        stage VARCHAR(32) NOT NULL DEFAULT 'shortlisted',
                        notes TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS project_moderation_queue (
                        id VARCHAR(36) PRIMARY KEY,
                        project_id VARCHAR(36) NOT NULL,
                        flagged_by VARCHAR(32) NOT NULL DEFAULT 'ai_safety_scanner',
                        reason_code VARCHAR(64) NOT NULL,
                        evidence_summary TEXT NOT NULL,
                        status VARCHAR(32) NOT NULL DEFAULT 'pending_review',
                        reviewer_id VARCHAR(36),
                        reviewer_notes TEXT,
                        appeal_details TEXT,
                        appealed_at DATETIME,
                        resolved_at DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            # Phase 15 Tables
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS project_invitations (
                        id VARCHAR(36) PRIMARY KEY,
                        project_id VARCHAR(36) NOT NULL,
                        org_id VARCHAR(36) NOT NULL,
                        freelancer_id VARCHAR(36) NOT NULL,
                        status VARCHAR(32) NOT NULL DEFAULT 'pending',
                        decline_reason VARCHAR(256),
                        invited_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        expires_at DATETIME NOT NULL,
                        responded_at DATETIME
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS project_applications (
                        id VARCHAR(36) PRIMARY KEY,
                        project_id VARCHAR(36) NOT NULL,
                        freelancer_id VARCHAR(36) NOT NULL,
                        status VARCHAR(32) NOT NULL DEFAULT 'submitted',
                        structured_pitch TEXT NOT NULL,
                        relevant_artifacts JSON,
                        proposed_rate REAL NOT NULL,
                        proposed_rate_period VARCHAR(32) NOT NULL DEFAULT 'fixed',
                        estimated_days INTEGER,
                        decline_reason VARCHAR(256),
                        withdrawn_at DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS project_conversations (
                        id VARCHAR(36) PRIMARY KEY,
                        project_id VARCHAR(36) NOT NULL,
                        org_id VARCHAR(36) NOT NULL,
                        freelancer_id VARCHAR(36) NOT NULL,
                        application_id VARCHAR(36),
                        status VARCHAR(32) NOT NULL DEFAULT 'active',
                        last_message_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS project_messages (
                        id VARCHAR(36) PRIMARY KEY,
                        conversation_id VARCHAR(36) NOT NULL,
                        sender_id VARCHAR(36) NOT NULL,
                        sender_role VARCHAR(32) NOT NULL,
                        body TEXT NOT NULL,
                        attachments JSON,
                        is_read BOOLEAN NOT NULL DEFAULT 0,
                        read_at DATETIME,
                        flagged_as_spam BOOLEAN NOT NULL DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS project_offers (
                        id VARCHAR(36) PRIMARY KEY,
                        project_id VARCHAR(36) NOT NULL,
                        application_id VARCHAR(36) NOT NULL,
                        conversation_id VARCHAR(36),
                        org_id VARCHAR(36) NOT NULL,
                        freelancer_id VARCHAR(36) NOT NULL,
                        creator_id VARCHAR(36) NOT NULL,
                        creator_role VARCHAR(32) NOT NULL,
                        version INTEGER NOT NULL DEFAULT 1,
                        status VARCHAR(32) NOT NULL DEFAULT 'pending_review',
                        contract_type VARCHAR(32) NOT NULL DEFAULT 'fixed_price',
                        agreed_amount REAL NOT NULL,
                        currency VARCHAR(8) NOT NULL DEFAULT 'USD',
                        milestones JSON,
                        scope_summary TEXT NOT NULL,
                        decision_deadline DATETIME NOT NULL,
                        rejection_reason VARCHAR(256),
                        lock_version INTEGER NOT NULL DEFAULT 1,
                        accepted_at DATETIME,
                        rejected_at DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS project_offer_revisions (
                        id VARCHAR(36) PRIMARY KEY,
                        offer_id VARCHAR(36) NOT NULL,
                        version INTEGER NOT NULL,
                        author_id VARCHAR(36) NOT NULL,
                        author_role VARCHAR(32) NOT NULL,
                        change_summary TEXT NOT NULL,
                        contract_type VARCHAR(32) NOT NULL,
                        agreed_amount REAL NOT NULL,
                        milestones JSON,
                        scope_summary TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS project_match_scores (
                        id VARCHAR(36) PRIMARY KEY,
                        project_id VARCHAR(36) NOT NULL,
                        freelancer_id VARCHAR(36) NOT NULL,
                        overall_score REAL NOT NULL,
                        skill_score REAL NOT NULL,
                        budget_score REAL NOT NULL,
                        availability_score REAL NOT NULL,
                        work_pref_score REAL NOT NULL,
                        newcomer_boost REAL NOT NULL DEFAULT 0.0,
                        breakdown_json JSON,
                        missing_information_json JSON,
                        hard_filter_passed BOOLEAN NOT NULL DEFAULT 1,
                        calculated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
        if await _table_columns(conn, "jobs", dialect):
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_jobs_created_at ON jobs (created_at)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_jobs_source_created ON jobs (source_name, created_at)"
                )
            )


async def _ensure_table_columns(
    conn: AsyncConnection,
    table: str,
    columns: dict[str, tuple[str, str]],
    dialect: str,
) -> None:
    existing = await _table_columns(conn, table, dialect)
    if not existing:
        return
    dialect_index = 0 if dialect == "sqlite" else 1
    for name, ddl_pair in columns.items():
        if name not in existing:
            try:
                await conn.execute(text(ddl_pair[dialect_index]))
                logger.info("Added missing column %s.%s", table, name)
            except Exception:
                logger.exception("Failed adding column %s.%s", table, name)


async def _table_columns(conn: AsyncConnection, table: str, dialect: str) -> set[str]:
    if dialect == "sqlite":
        result = await conn.execute(text(f"PRAGMA table_info({table})"))
        return {row[1] for row in result.fetchall()}
    result = await conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :table"
        ),
        {"table": table},
    )
    return {row[0] for row in result.fetchall()}
