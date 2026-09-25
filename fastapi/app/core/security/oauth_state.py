from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import jwt

from config.settings import get_settings

_OAUTH_STATE_PURPOSE = "upwork_oauth"


def create_upwork_oauth_state(ttl_minutes: int = 15) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    payload = {
        "purpose": _OAUTH_STATE_PURPOSE,
        "nonce": secrets.token_urlsafe(16),
        "exp": expires,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def validate_upwork_oauth_state(state: str | None) -> None:
    if not state:
        raise ValueError("Missing OAuth state")
    settings = get_settings()
    try:
        payload = jwt.decode(state, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError as exc:
        raise ValueError("Invalid or expired OAuth state") from exc
    if payload.get("purpose") != _OAUTH_STATE_PURPOSE:
        raise ValueError("Invalid OAuth state purpose")
