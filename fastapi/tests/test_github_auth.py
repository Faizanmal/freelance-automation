from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pyotp
from app.api.v1.auth import get_github_auth_url, github_auth
from app.core.security.github_auth import GitHubAuthService
from app.core.security.oauth_state import (
    create_github_oauth_state,
    validate_github_oauth_state,
)
from app.schemas.user import GitHubAuthRequest
from fastapi import HTTPException


def _user(**overrides: object) -> SimpleNamespace:
    now = datetime.now(UTC)
    base = {
        "id": "u1",
        "email": "user@example.com",
        "full_name": "Test User",
        "hashed_password": "hashed_password",
        "google_id": None,
        "github_id": None,
        "is_active": True,
        "is_verified": False,
        "is_superuser": False,
        "totp_secret": None,
        "is_totp_enabled": False,
        "plan": "free",
        "subscription_status": "inactive",
        "timezone": None,
        "locale": None,
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class GitHubAuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_github_auth_url_success(self) -> None:
        settings = SimpleNamespace(
            github_client_id="test-github-client-id",
            github_redirect_uri="http://localhost:3000/auth/callback/github",
            public_app_url="http://localhost:3000",
            jwt_secret_key="dev-secret-key-32-chars-long-test-1234",
            jwt_algorithm="HS256",
        )
        with patch("app.core.security.github_auth.get_settings", return_value=settings):
            with patch("app.core.security.oauth_state.get_settings", return_value=settings):
                response = await get_github_auth_url()

        self.assertIn("https://github.com/login/oauth/authorize", response.url)
        self.assertIn("client_id=test-github-client-id", response.url)
        self.assertIn("state=", response.url)
        self.assertTrue(response.state)

        with patch("app.core.security.oauth_state.get_settings", return_value=settings):
            validate_github_oauth_state(response.state)

    async def test_get_github_auth_url_not_configured(self) -> None:
        settings = SimpleNamespace(
            github_client_id=None,
            github_redirect_uri=None,
            public_app_url="http://localhost:3000",
        )
        with patch("app.core.security.github_auth.get_settings", return_value=settings):
            with self.assertRaises(HTTPException) as ctx:
                await get_github_auth_url()
        self.assertEqual(ctx.exception.status_code, 503)

    async def test_github_auth_new_user(self) -> None:
        github_info = {
            "sub": "github-123",
            "email": "octocat@github.com",
            "name": "The Octocat",
            "picture": "https://avatars.githubusercontent.com/u/1",
        }

        created = _user(
            id="new-gh-u1",
            email="octocat@github.com",
            full_name="The Octocat",
            github_id="github-123",
            is_verified=True,
        )

        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()

        repo = MagicMock()
        repo.get_by_github_id = AsyncMock(return_value=None)
        repo.get_by_email = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=created)

        settings = SimpleNamespace(
            access_token_expire_minutes=60,
            jwt_secret_key="dev-secret-key-32-chars-long-test-1234",
            jwt_algorithm="HS256",
        )

        with (
            patch("app.api.v1.auth.auth_rate_limiter.check", new=AsyncMock()),
            patch("app.api.v1.auth.client_ip", return_value="127.0.0.1"),
            patch("app.api.v1.auth.GitHubAuthService.exchange_code_for_user", AsyncMock(return_value=github_info)),
            patch("app.api.v1.auth.SQLAlchemyUserRepository", return_value=repo),
            patch("app.api.v1.auth.get_settings", return_value=settings),
            patch("app.core.security.jwt.get_settings", return_value=settings),
        ):
            payload = GitHubAuthRequest(code="gh-code-123", state="gh-state-123")
            token_resp = await github_auth(
                request=MagicMock(),
                payload=payload,
                session=session,
            )

        self.assertTrue(token_resp.access_token)
        session.add.assert_called_once()  # UserPreferences created
        session.commit.assert_called()

    async def test_github_auth_links_existing_user(self) -> None:
        github_info = {
            "sub": "github-456",
            "email": "existing@example.com",
            "name": "Octo User",
        }

        existing_user = _user(
            id="u-existing-gh",
            email="existing@example.com",
            full_name=None,
            github_id=None,
            is_verified=False,
        )

        session = AsyncMock()
        repo = MagicMock()
        repo.get_by_github_id = AsyncMock(return_value=None)
        repo.get_by_email = AsyncMock(return_value=existing_user)
        repo.update = AsyncMock(return_value=existing_user)

        settings = SimpleNamespace(
            access_token_expire_minutes=60,
            jwt_secret_key="dev-secret-key-32-chars-long-test-1234",
            jwt_algorithm="HS256",
        )

        with (
            patch("app.api.v1.auth.auth_rate_limiter.check", new=AsyncMock()),
            patch("app.api.v1.auth.client_ip", return_value="127.0.0.1"),
            patch("app.api.v1.auth.GitHubAuthService.exchange_code_for_user", AsyncMock(return_value=github_info)),
            patch("app.api.v1.auth.SQLAlchemyUserRepository", return_value=repo),
            patch("app.api.v1.auth.get_settings", return_value=settings),
            patch("app.core.security.jwt.get_settings", return_value=settings),
        ):
            payload = GitHubAuthRequest(code="gh-code-123")
            token_resp = await github_auth(
                request=MagicMock(),
                payload=payload,
                session=session,
            )

        self.assertTrue(token_resp.access_token)
        self.assertEqual(existing_user.github_id, "github-456")
        self.assertTrue(existing_user.is_verified)
        self.assertEqual(existing_user.full_name, "Octo User")

    async def test_github_auth_totp_enforcement(self) -> None:
        totp_secret = pyotp.random_base32()
        existing_user = _user(
            id="u-totp-gh",
            email="totpgh@example.com",
            github_id="github-789",
            is_verified=True,
            is_totp_enabled=True,
            totp_secret=totp_secret,
        )

        session = AsyncMock()
        repo = MagicMock()
        repo.get_by_github_id = AsyncMock(return_value=existing_user)
        repo.update = AsyncMock(return_value=existing_user)

        github_info = {
            "sub": "github-789",
            "email": "totpgh@example.com",
        }

        settings = SimpleNamespace(
            access_token_expire_minutes=60,
            jwt_secret_key="dev-secret-key-32-chars-long-test-1234",
            jwt_algorithm="HS256",
        )

        with (
            patch("app.api.v1.auth.auth_rate_limiter.check", new=AsyncMock()),
            patch("app.api.v1.auth.client_ip", return_value="127.0.0.1"),
            patch("app.api.v1.auth.GitHubAuthService.exchange_code_for_user", AsyncMock(return_value=github_info)),
            patch("app.api.v1.auth.SQLAlchemyUserRepository", return_value=repo),
            patch("app.api.v1.auth.get_settings", return_value=settings),
            patch("app.core.security.jwt.get_settings", return_value=settings),
        ):
            # Missing TOTP
            with self.assertRaises(HTTPException) as ctx:
                await github_auth(
                    request=MagicMock(),
                    payload=GitHubAuthRequest(code="code"),
                    session=session,
                )
            self.assertEqual(ctx.exception.status_code, 401)
            self.assertEqual(ctx.exception.detail, "TOTP_REQUIRED")

            # Valid TOTP
            valid_code = pyotp.TOTP(totp_secret).now()
            token_resp = await github_auth(
                request=MagicMock(),
                payload=GitHubAuthRequest(code="code", totp_code=valid_code),
                session=session,
            )
            self.assertTrue(token_resp.access_token)

    async def test_github_auth_state_validation(self) -> None:
        settings = SimpleNamespace(
            jwt_secret_key="dev-secret-key-32-chars-long-test-1234",
            jwt_algorithm="HS256",
        )
        with patch("app.core.security.oauth_state.get_settings", return_value=settings):
            state = create_github_oauth_state()
            validate_github_oauth_state(state)

            with self.assertRaises(ValueError):
                validate_github_oauth_state(None)

            with self.assertRaises(ValueError):
                validate_github_oauth_state("invalid.jwt.token")
