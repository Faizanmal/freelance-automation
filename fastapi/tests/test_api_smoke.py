"""Optional live API smoke — skipped unless LIVE_API_URL is set and reachable."""

from __future__ import annotations

import os
import unittest

import httpx

LIVE_API = os.getenv("LIVE_API_URL", "").rstrip("/")


@unittest.skipUnless(LIVE_API, "Set LIVE_API_URL to run live API smoke tests")
class LiveApiSmokeTests(unittest.TestCase):
    def test_health_live(self) -> None:
        # Accept either root or /api/v1 health mounts.
        candidates = [
            f"{LIVE_API}/health/live",
            f"{LIVE_API.replace('/api/v1', '')}/health/live",
        ]
        last_error: Exception | None = None
        for url in candidates:
            try:
                response = httpx.get(url, timeout=10.0)
                if response.status_code == 200:
                    self.assertIn(
                        response.json().get("status"), {"ok", "alive", "live", None}
                    )
                    return
            except httpx.HTTPError as exc:
                last_error = exc
        self.fail(f"Health check failed for {candidates}: {last_error}")

    def test_register_login_scrape_happy_path(self) -> None:
        import random
        import string

        suffix = "".join(random.choices(string.ascii_lowercase, k=8))
        email = f"smoke_{suffix}@example.com"
        password = "SecurePassword123!"
        base = LIVE_API if LIVE_API.endswith("/api/v1") else f"{LIVE_API}/api/v1"

        register = httpx.post(
            f"{base}/auth/register",
            json={"email": email, "password": password, "full_name": "Smoke"},
            timeout=20.0,
        )
        self.assertIn(register.status_code, {200, 201})

        login = httpx.post(
            f"{base}/auth/login",
            data={"username": email, "password": password},
            timeout=20.0,
        )
        self.assertEqual(login.status_code, 200)
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Ensure verified for scrape (dev auto-verify or explicit).
        body = register.json()
        if not body.get("is_verified") and not body.get("auto_verified"):
            httpx.post(f"{base}/auth/dev-verify", headers=headers, timeout=10.0)

        scrape = httpx.post(
            f"{base}/jobs/scrape",
            headers=headers,
            json={"sources": ["remoteok"], "limit": 5, "background": False},
            timeout=120.0,
        )
        self.assertEqual(scrape.status_code, 200, scrape.text)
        payload = scrape.json()
        self.assertEqual(payload.get("status"), "completed")
        self.assertIn("total_fetched", payload)


if __name__ == "__main__":
    unittest.main()
