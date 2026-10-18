from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from config.settings import get_settings

settings = get_settings()


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expires = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {
        "sub": str(subject),
        "exp": expires,
        "iat": datetime.now(UTC),
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return token


def decode_access_token(token: str) -> dict[str, str]:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        subject = payload.get("sub")
        if subject is None:
            raise jwt.InvalidTokenError("Missing subject")
        return payload
    except jwt.InvalidTokenError as exc:
        raise jwt.InvalidTokenError("Could not validate credentials") from exc


def create_password_reset_token(email: str) -> str:
    expires = datetime.now(UTC) + timedelta(minutes=15)
    payload = {
        "sub": email,
        "exp": expires,
        "iat": datetime.now(UTC),
        "scope": "password_reset",
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_password_reset_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("scope") != "password_reset":
            raise jwt.InvalidTokenError("Invalid token scope")
        email = payload.get("sub")
        if not email:
            raise jwt.InvalidTokenError("Missing subject")
        return email
    except jwt.InvalidTokenError as exc:
        raise jwt.InvalidTokenError("Invalid or expired password reset token") from exc


def create_email_verification_token(email: str) -> str:
    expires = datetime.now(UTC) + timedelta(hours=24)
    payload = {
        "sub": email,
        "exp": expires,
        "iat": datetime.now(UTC),
        "scope": "email_verification",
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_email_verification_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("scope") != "email_verification":
            raise jwt.InvalidTokenError("Invalid token scope")
        email = payload.get("sub")
        if not email:
            raise jwt.InvalidTokenError("Missing subject")
        return email
    except jwt.InvalidTokenError as exc:
        raise jwt.InvalidTokenError(
            "Invalid or expired email verification token"
        ) from exc
