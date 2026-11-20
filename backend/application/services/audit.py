"""Sensitive-operation audit trail (no raw secrets or résumé bodies)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def record_audit(
    session: AsyncSession | None,
    *,
    action: str,
    user_id: str | None = None,
    actor_ip: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """
    Persist an audit row when the model is available; always structured-log.
    Meta must not include passwords, tokens, or full contact payloads.
    """
    safe_meta = {k: v for k, v in (meta or {}).items() if k not in {"password", "token", "secret", "authorization"}}
    logger.info(
        "audit action=%s user_id=%s ip=%s meta=%s",
        action,
        user_id or "-",
        actor_ip or "-",
        safe_meta,
    )
    if session is None:
        return
    try:
        from database.models.audit import AuditEvent

        session.add(
            AuditEvent(
                action=action,
                user_id=user_id,
                actor_ip=(actor_ip or "")[:64] or None,
                meta=safe_meta or None,
            )
        )
        # Caller owns commit for request transactions; flush so row is visible.
        await session.flush()
    except Exception:  # noqa: BLE001 — audit must never break the primary flow
        logger.exception("audit_persist_failed action=%s", action)
