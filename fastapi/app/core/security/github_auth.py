from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx
from app.core.logging.logger import get_logger
from app.core.security.oauth_state import (
    create_github_oauth_state,
    validate_github_oauth_state,
)
from config.settings import get_settings
from fastapi import HTTPException, status

logger = get_logger(__name__)

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


class GitHubAuthService:
    @staticmethod
    def get_authorization_url(redirect_uri: str | None = None) -> tuple[str, str]:
        settings = get_settings()
        if not settings.github_client_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GitHub Sign-In is not configured on this server.",
            )

        resolved_redirect_uri = (
            redirect_uri
            or settings.github_redirect_uri
            or f"{settings.public_app_url.rstrip('/')}/auth/callback/github"
        )
        state = create_github_oauth_state()
        params = {
            "client_id": settings.github_client_id,
            "redirect_uri": resolved_redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
        url = f"{GITHUB_AUTH_URL}?{urlencode(params)}"
        return url, state

    @staticmethod
    async def exchange_code_for_user(
        code: str,
        state: str | None = None,
        redirect_uri: str | None = None,
    ) -> dict[str, Any]:
        """
        Validate state and exchange GitHub authorization code for user info.
        """
        if state:
            try:
                validate_github_oauth_state(state)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"OAuth state validation failed: {exc}",
                ) from exc

        settings = get_settings()
        if not settings.github_client_id or not settings.github_client_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GitHub OAuth credentials are not fully configured.",
            )

        resolved_redirect_uri = (
            redirect_uri
            or settings.github_redirect_uri
            or f"{settings.public_app_url.rstrip('/')}/auth/callback/github"
        )

        data = {
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret,
            "code": code,
            "redirect_uri": resolved_redirect_uri,
        }
        headers = {
            "Accept": "application/json",
            "User-Agent": "SignalDesk-Auth",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                token_resp = await client.post(GITHUB_TOKEN_URL, data=data, headers=headers)
            except Exception as exc:
                logger.warning("Failed to contact GitHub token exchange: %s", exc)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Could not reach GitHub token service.",
                ) from exc

            if token_resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange authorization code with GitHub.",
                )

            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                error_msg = token_data.get("error_description") or "GitHub authorization failed."
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg,
                )

            auth_headers = {
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "SignalDesk-Auth",
                "Accept": "application/vnd.github+json",
            }

            try:
                user_resp = await client.get(GITHUB_USER_URL, headers=auth_headers)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Could not fetch GitHub user profile.",
                ) from exc

            if user_resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to retrieve GitHub user profile.",
                )

            user_data = user_resp.json()
            github_id = str(user_data["id"])
            email = user_data.get("email")

            # If user email is private on GitHub profile, fetch from emails endpoint
            if not email:
                try:
                    emails_resp = await client.get(GITHUB_EMAILS_URL, headers=auth_headers)
                    if emails_resp.status_code == 200:
                        emails_data = emails_resp.json()
                        # Find primary verified email
                        for item in emails_data:
                            if item.get("primary") and item.get("verified"):
                                email = item.get("email")
                                break
                        # Fallback to any verified email
                        if not email:
                            for item in emails_data:
                                if item.get("verified"):
                                    email = item.get("email")
                                    break
                except Exception as exc:
                    logger.warning("Failed to fetch GitHub user emails: %s", exc)

            if not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No verified email address found on GitHub account.",
                )

            return {
                "sub": github_id,
                "email": str(email).lower().strip(),
                "name": user_data.get("name") or user_data.get("login"),
                "picture": user_data.get("avatar_url"),
            }
