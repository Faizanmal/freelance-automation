from __future__ import annotations

from app.core.logging.logger import get_logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

logger = get_logger(__name__)

JOB_COLUMNS = {
    "location": "ALTER TABLE jobs ADD COLUMN location VARCHAR(256)",
    "tags": "ALTER TABLE jobs ADD COLUMN tags JSON",
    "seniority": "ALTER TABLE jobs ADD COLUMN seniority VARCHAR(64)",
    "analysis_summary": "ALTER TABLE jobs ADD COLUMN analysis_summary TEXT",
    "enrichment": "ALTER TABLE jobs ADD COLUMN enrichment JSON",
}

USER_COLUMNS = {
    "plan": "ALTER TABLE users ADD COLUMN plan VARCHAR(32) DEFAULT 'free'",
    "subscription_status": "ALTER TABLE users ADD COLUMN subscription_status VARCHAR(32) DEFAULT 'inactive'",
    "stripe_customer_id": "ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR(128)",
    "stripe_subscription_id": "ALTER TABLE users ADD COLUMN stripe_subscription_id VARCHAR(128)",
}

PREFERENCE_COLUMNS = {
    "alert_email": "ALTER TABLE user_preferences ADD COLUMN alert_email VARCHAR(256)",
    "slack_webhook_url": "ALTER TABLE user_preferences ADD COLUMN slack_webhook_url VARCHAR(1024)",
    "telegram_chat_id": "ALTER TABLE user_preferences ADD COLUMN telegram_chat_id VARCHAR(128)",
    "discord_webhook_url": "ALTER TABLE user_preferences ADD COLUMN discord_webhook_url VARCHAR(1024)",
    "whatsapp_to": "ALTER TABLE user_preferences ADD COLUMN whatsapp_to VARCHAR(64)",
}


async def ensure_sqlite_columns(engine: AsyncEngine) -> None:
    """Best-effort ALTER for existing SQLite DBs created before new columns existed."""
    if "sqlite" not in str(engine.url):
        return
    async with engine.begin() as conn:
        await _ensure_table_columns(conn, "jobs", JOB_COLUMNS)
        await _ensure_table_columns(conn, "users", USER_COLUMNS)
        await _ensure_table_columns(conn, "user_preferences", PREFERENCE_COLUMNS)


async def _ensure_table_columns(conn: AsyncConnection, table: str, columns: dict[str, str]) -> None:
    existing = await _sqlite_columns(conn, table)
    if not existing:
        return
    for name, ddl in columns.items():
        if name not in existing:
            try:
                await conn.execute(text(ddl))
                logger.info("Added missing column %s.%s", table, name)
            except Exception:
                logger.exception("Failed adding column %s.%s", table, name)


async def _sqlite_columns(conn: AsyncConnection, table: str) -> set[str]:
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    return {row[1] for row in result.fetchall()}
