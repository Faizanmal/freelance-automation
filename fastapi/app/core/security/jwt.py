from __future__ import annotations

from datetime import datetime, timedelta

import jwt

from config.settings import get_settings


settings = get_settings()


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expires = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload = {
        "sub": str(subject),
        "exp": expires,
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token


def decode_access_token(token: str) -> dict[str, str]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        subject = payload.get("sub")
        if subject is None:
            raise jwt.InvalidTokenError("Missing subject")
        return payload
    except jwt.InvalidTokenError as exc:
        raise jwt.InvalidTokenError("Could not validate credentials") from exc
