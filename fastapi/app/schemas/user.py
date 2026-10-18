from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None
    timezone: str | None = None
    locale: str | None = None


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRead(UserBase):
    id: str
    is_active: bool
    is_verified: bool = False
    is_superuser: bool = False
    is_totp_enabled: bool = False
    plan: str = "free"
    subscription_status: str = "inactive"
    created_at: datetime
    updated_at: datetime
    verification_email_sent: bool | None = None
    auto_verified: bool | None = None
    verify_url: str | None = None
    detail: str | None = None

    model_config = {
        "from_attributes": True,
    }


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class Setup2FAResponse(BaseModel):
    secret: str
    provisioning_uri: str


class Verify2FARequest(BaseModel):
    code: str
