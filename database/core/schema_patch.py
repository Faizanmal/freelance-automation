from __future__ import annotations

from app.core.logging.logger import get_logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

logger = get_logger(__name__)

# Column name → (sqlite DDL, postgresql DDL). Only one dialect's statement is run.
JOB_COLUMNS = {
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
