from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx
from app.core.logging.logger import get_logger
from app.core.security.oauth_state import (
    create_google_oauth_state,
    validate_google_oauth_state,
)
from config.settings import get_settings
from fastapi import HTTPException, status

logger = get_logger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleAuthService:
    @staticmethod
    def get_authorization_url(redirect_uri: str | None = None) -> tuple[str, str]:
        settings = get_settings()
        if not settings.google_client_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google Sign-In is not configured on this server.",
            )

        resolved_redirect_uri = (
            redirect_uri
            or settings.google_redirect_uri
            or f"{settings.public_app_url.rstrip('/')}/auth/callback/google"
        )
        state = create_google_oauth_state()
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": resolved_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "state": state,
            "prompt": "select_account consent",
        }
        url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
        return url, state

    @staticmethod
    async def verify_id_token(id_token: str) -> dict[str, Any]:
        """
        Verify a Google ID token via Google's tokeninfo endpoint.
        Validates iss, aud, email_verified, and essential user fields.
        """
        settings = get_settings()
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    GOOGLE_TOKENINFO_URL, params={"id_token": id_token}
                )
            except Exception as exc:
                logger.warning("Failed to contact Google tokeninfo: %s", exc)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Could not reach Google verification service.",
                ) from exc

        if resp.status_code != 200:
            logger.warning("Google tokeninfo returned status %d", resp.status_code)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Google ID token.",
            )

        payload = resp.json()

        iss = payload.get("iss")
        if iss not in ("accounts.google.com", "https://accounts.google.com"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Google token issuer.",
            )

        if settings.google_client_id:
            aud = payload.get("aud")
            if aud != settings.google_client_id:
                logger.warning("Google token audience mismatch")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google token audience mismatch.",
                )

        email_verified = payload.get("email_verified")
        if email_verified not in (True, "true", "True", 1, "1"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google email address is not verified.",
            )

        email = payload.get("email")
        sub = payload.get("sub")
        if not email or not sub:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google token missing essential user identifiers.",
            )

        return {
            "sub": str(sub),
            "email": str(email).lower().strip(),
            "name": payload.get("name"),
            "picture": payload.get("picture"),
        }

    @staticmethod
    async def exchange_code_for_user(
        code: str,
        state: str | None = None,
        redirect_uri: str | None = None,
    ) -> dict[str, Any]:
        """
        Validate state and exchange authorization code for verified user info.
        """
        if state:
            try:
                validate_google_oauth_state(state)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"OAuth state validation failed: {exc}",
                ) from exc

        settings = get_settings()
        if not settings.google_client_id or not settings.google_client_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google OAuth credentials are not fully configured.",
            )

        resolved_redirect_uri = (
            redirect_uri
            or settings.google_redirect_uri
            or f"{settings.public_app_url.rstrip('/')}/auth/callback/google"
        )

        data = {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": resolved_redirect_uri,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                token_resp = await client.post(GOOGLE_TOKEN_URL, data=data)
            except Exception as exc:
                logger.warning("Failed to contact Google token exchange: %s", exc)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Could not reach Google token endpoint.",
                ) from exc

            if token_resp.status_code != 200:
                logger.warning("Google token exchange error status: %d", token_resp.status_code)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange authorization code with Google.",
                )

            token_data = token_resp.json()
            id_token = token_data.get("id_token")
            access_token = token_data.get("access_token")

            if id_token:
                return await GoogleAuthService.verify_id_token(id_token)

            if not access_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No access token or ID token returned by Google.",
                )

            try:
                userinfo_resp = await client.get(
                    GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Could not fetch user profile from Google.",
                ) from exc

            if userinfo_resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to retrieve user info from Google.",
                )

            userinfo = userinfo_resp.json()
            email_verified = userinfo.get("email_verified")
            if email_verified not in (True, "true", "True", 1, "1"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google email address is not verified.",
                )

            return {
                "sub": str(userinfo["sub"]),
                "email": str(userinfo["email"]).lower().strip(),
                "name": userinfo.get("name"),
                "picture": userinfo.get("picture"),
            }

