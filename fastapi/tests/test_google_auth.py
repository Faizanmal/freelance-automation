from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pyotp
from app.api.v1.auth import get_google_auth_url, google_auth
from app.core.security.google_auth import GoogleAuthService
from app.core.security.oauth_state import (
    create_google_oauth_state,
    validate_google_oauth_state,
)
from app.schemas.user import GoogleAuthRequest
from fastapi import HTTPException


def _user(**overrides: object) -> SimpleNamespace:
    now = datetime.now(UTC)
    base = {
        "id": "u1",
        "email": "user@example.com",
        "full_name": "Test User",
        "hashed_password": "hashed_password",
        "google_id": None,
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


class GoogleAuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_google_auth_url_success(self) -> None:
        settings = SimpleNamespace(
            google_client_id="test-google-client-id",
            google_redirect_uri="http://localhost:3000/auth/callback/google",
            public_app_url="http://localhost:3000",
            jwt_secret_key="dev-secret-key-32-chars-long-test-1234",
            jwt_algorithm="HS256",
        )
        with patch("app.core.security.google_auth.get_settings", return_value=settings):
            with patch("app.core.security.oauth_state.get_settings", return_value=settings):
                response = await get_google_auth_url()

        self.assertIn("https://accounts.google.com/o/oauth2/v2/auth", response.url)
        self.assertIn("client_id=test-google-client-id", response.url)
        self.assertIn("response_type=code", response.url)
        self.assertIn("state=", response.url)
        self.assertTrue(response.state)

        with patch("app.core.security.oauth_state.get_settings", return_value=settings):
            # Should not raise
            validate_google_oauth_state(response.state)

    async def test_get_google_auth_url_not_configured(self) -> None:
        settings = SimpleNamespace(
            google_client_id=None,
            google_redirect_uri=None,
            public_app_url="http://localhost:3000",
        )
        with patch("app.core.security.google_auth.get_settings", return_value=settings):
            with self.assertRaises(HTTPException) as ctx:
                await get_google_auth_url()
        self.assertEqual(ctx.exception.status_code, 503)

    async def test_google_auth_with_id_token_new_user(self) -> None:
        google_info = {
            "sub": "google-sub-123",
            "email": "newgoogle@example.com",
            "name": "New Google User",
            "picture": "https://example.com/photo.jpg",
        }

        created = _user(
            id="new-u1",
            email="newgoogle@example.com",
            full_name="New Google User",
            google_id="google-sub-123",
            is_verified=True,
        )

        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()

        repo = MagicMock()
        repo.get_by_google_id = AsyncMock(return_value=None)
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
            patch("app.api.v1.auth.GoogleAuthService.verify_id_token", AsyncMock(return_value=google_info)),
            patch("app.api.v1.auth.SQLAlchemyUserRepository", return_value=repo),
            patch("app.api.v1.auth.get_settings", return_value=settings),
            patch("app.core.security.jwt.get_settings", return_value=settings),
        ):
            payload = GoogleAuthRequest(id_token="valid-id-token")
            token_resp = await google_auth(
                request=MagicMock(),
                payload=payload,
                session=session,
            )

        self.assertTrue(token_resp.access_token)
        session.add.assert_called_once()  # UserPreferences added
        session.commit.assert_called()

    async def test_google_auth_links_existing_user_by_email(self) -> None:
        google_info = {
            "sub": "google-sub-456",
            "email": "existing@example.com",
            "name": "Existing User",
        }

        existing_user = _user(
            id="u-existing",
            email="existing@example.com",
            full_name=None,
            google_id=None,
            is_verified=False,
        )

        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        repo = MagicMock()
        repo.get_by_google_id = AsyncMock(return_value=None)
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
            patch("app.api.v1.auth.GoogleAuthService.verify_id_token", AsyncMock(return_value=google_info)),
            patch("app.api.v1.auth.SQLAlchemyUserRepository", return_value=repo),
            patch("app.api.v1.auth.get_settings", return_value=settings),
            patch("app.core.security.jwt.get_settings", return_value=settings),
        ):
            payload = GoogleAuthRequest(id_token="valid-id-token")
            token_resp = await google_auth(
                request=MagicMock(),
                payload=payload,
                session=session,
            )

        self.assertTrue(token_resp.access_token)
        self.assertEqual(existing_user.google_id, "google-sub-456")
        self.assertTrue(existing_user.is_verified)
        self.assertEqual(existing_user.full_name, "Existing User")

    async def test_google_auth_totp_enforcement(self) -> None:
        totp_secret = pyotp.random_base32()
        existing_user = _user(
            id="u-totp",
            email="totpuser@example.com",
            google_id="google-sub-789",
            is_verified=True,
            is_totp_enabled=True,
            totp_secret=totp_secret,
        )

        session = AsyncMock()
        repo = MagicMock()
        repo.get_by_google_id = AsyncMock(return_value=existing_user)
        repo.update = AsyncMock(return_value=existing_user)

        google_info = {
            "sub": "google-sub-789",
            "email": "totpuser@example.com",
        }

        settings = SimpleNamespace(
            access_token_expire_minutes=60,
            jwt_secret_key="dev-secret-key-32-chars-long-test-1234",
            jwt_algorithm="HS256",
        )

        with (
            patch("app.api.v1.auth.auth_rate_limiter.check", new=AsyncMock()),
            patch("app.api.v1.auth.client_ip", return_value="127.0.0.1"),
            patch("app.api.v1.auth.GoogleAuthService.verify_id_token", AsyncMock(return_value=google_info)),
            patch("app.api.v1.auth.SQLAlchemyUserRepository", return_value=repo),
            patch("app.api.v1.auth.get_settings", return_value=settings),
            patch("app.core.security.jwt.get_settings", return_value=settings),
        ):
            # 1. Calling without TOTP code raises 401 TOTP_REQUIRED
            with self.assertRaises(HTTPException) as ctx:
                await google_auth(
                    request=MagicMock(),
                    payload=GoogleAuthRequest(id_token="valid-id-token"),
                    session=session,
                )
            self.assertEqual(ctx.exception.status_code, 401)
            self.assertEqual(ctx.exception.detail, "TOTP_REQUIRED")

            # 2. Calling with invalid TOTP code raises 401 Invalid TOTP code
            with self.assertRaises(HTTPException) as ctx:
                await google_auth(
                    request=MagicMock(),
                    payload=GoogleAuthRequest(id_token="valid-id-token", totp_code="000000"),
                    session=session,
                )
            self.assertEqual(ctx.exception.status_code, 401)
            self.assertIn("Invalid TOTP code", ctx.exception.detail)

            # 3. Calling with valid TOTP code succeeds
            valid_totp = pyotp.TOTP(totp_secret).now()
            token_resp = await google_auth(
                request=MagicMock(),
                payload=GoogleAuthRequest(id_token="valid-id-token", totp_code=valid_totp),
                session=session,
            )
            self.assertTrue(token_resp.access_token)

    async def test_google_auth_disabled_account_forbidden(self) -> None:
        existing_user = _user(
            id="u-disabled",
            email="disabled@example.com",
            google_id="google-sub-disabled",
            is_verified=True,
            is_active=False,
        )

        session = AsyncMock()
        repo = MagicMock()
        repo.get_by_google_id = AsyncMock(return_value=existing_user)
        repo.update = AsyncMock(return_value=existing_user)

        google_info = {
            "sub": "google-sub-disabled",
            "email": "disabled@example.com",
        }

        with (
            patch("app.api.v1.auth.auth_rate_limiter.check", new=AsyncMock()),
            patch("app.api.v1.auth.client_ip", return_value="127.0.0.1"),
            patch("app.api.v1.auth.GoogleAuthService.verify_id_token", AsyncMock(return_value=google_info)),
            patch("app.api.v1.auth.SQLAlchemyUserRepository", return_value=repo),
        ):
            with self.assertRaises(HTTPException) as ctx:
                await google_auth(
                    request=MagicMock(),
                    payload=GoogleAuthRequest(id_token="valid-token"),
                    session=session,
                )
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertIn("disabled", ctx.exception.detail)

    async def test_google_auth_missing_credentials(self) -> None:
        session = AsyncMock()
        with (
            patch("app.api.v1.auth.auth_rate_limiter.check", new=AsyncMock()),
            patch("app.api.v1.auth.client_ip", return_value="127.0.0.1"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                await google_auth(
                    request=MagicMock(),
                    payload=GoogleAuthRequest(),
                    session=session,
                )
            self.assertEqual(ctx.exception.status_code, 400)

    async def test_google_auth_code_exchange(self) -> None:
        google_info = {
            "sub": "google-sub-code",
            "email": "codeuser@example.com",
            "name": "Code User",
        }

        user_obj = _user(
            id="u-code",
            email="codeuser@example.com",
            google_id="google-sub-code",
            is_verified=True,
        )

        session = AsyncMock()
        repo = MagicMock()
        repo.get_by_google_id = AsyncMock(return_value=user_obj)
        repo.update = AsyncMock(return_value=user_obj)

        settings = SimpleNamespace(
            access_token_expire_minutes=60,
            jwt_secret_key="dev-secret-key-32-chars-long-test-1234",
            jwt_algorithm="HS256",
        )

        with (
            patch("app.api.v1.auth.auth_rate_limiter.check", new=AsyncMock()),
            patch("app.api.v1.auth.client_ip", return_value="127.0.0.1"),
            patch("app.api.v1.auth.GoogleAuthService.exchange_code_for_user", AsyncMock(return_value=google_info)),
            patch("app.api.v1.auth.SQLAlchemyUserRepository", return_value=repo),
            patch("app.api.v1.auth.get_settings", return_value=settings),
            patch("app.core.security.jwt.get_settings", return_value=settings),
        ):
            payload = GoogleAuthRequest(code="google-auth-code", state="state-token")
            token_resp = await google_auth(
                request=MagicMock(),
                payload=payload,
                session=session,
            )
            self.assertTrue(token_resp.access_token)

    async def test_google_auth_state_validation(self) -> None:
        settings = SimpleNamespace(
            jwt_secret_key="dev-secret-key-32-chars-long-test-1234",
            jwt_algorithm="HS256",
        )
        with patch("app.core.security.oauth_state.get_settings", return_value=settings):
            state = create_google_oauth_state(ttl_minutes=15)
            # Valid state doesn't raise
            validate_google_oauth_state(state)

            # Missing state raises ValueError
            with self.assertRaises(ValueError):
                validate_google_oauth_state(None)

            # Tampered state raises ValueError
            with self.assertRaises(ValueError):
                validate_google_oauth_state("tampered.state.jwt")

    async def test_verify_id_token_audience_mismatch(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "iss": "accounts.google.com",
            "aud": "wrong-client-id",
            "email": "user@example.com",
            "email_verified": True,
            "sub": "sub123",
        }

        settings = SimpleNamespace(
            google_client_id="expected-client-id",
        )

        with patch("app.core.security.google_auth.get_settings", return_value=settings):
            with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_response)):
                with self.assertRaises(HTTPException) as ctx:
                    await GoogleAuthService.verify_id_token("token123")
                self.assertEqual(ctx.exception.status_code, 400)
                self.assertIn("audience mismatch", ctx.exception.detail)

    async def test_verify_id_token_unverified_email(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "iss": "accounts.google.com",
            "aud": "expected-client-id",
            "email": "user@example.com",
            "email_verified": False,
            "sub": "sub123",
        }

        settings = SimpleNamespace(
            google_client_id="expected-client-id",
        )

        with patch("app.core.security.google_auth.get_settings", return_value=settings):
            with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_response)):
                with self.assertRaises(HTTPException) as ctx:
                    await GoogleAuthService.verify_id_token("token123")
                self.assertEqual(ctx.exception.status_code, 400)
                self.assertIn("not verified", ctx.exception.detail)
