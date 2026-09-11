from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = Field("bearer")
    expires_at: datetime


class TokenPayload(BaseModel):
    sub: str
    exp: int
    iat: int
