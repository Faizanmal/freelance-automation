from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = Field("bearer")
    expires_at: datetime
    refresh_token: str | None = None
    refresh_expires_at: datetime | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str | None = None


class TokenPayload(BaseModel):
    sub: str
    exp: int
    iat: int
