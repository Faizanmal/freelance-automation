import os
import random
import string
import sys

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def get_random_string(length):
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for i in range(length))


def main():
    base_url = os.environ.get("API_URL", "http://localhost:8000/api/v1")
    print(f"Starting Live E2E Tests against: {base_url}")

    # 1. Test Health
    try:
        res = requests.get(f"{base_url.replace('/api/v1', '')}/health/live")
        res.raise_for_status()
        print("✅ Health Check Passed")
    except requests.RequestException as e:
        print(f"❌ Health Check Failed: {e}")
        sys.exit(1)

    # 2. Register
    test_email = f"test_{get_random_string(8)}@example.com"
    test_password = "SecurePassword123!"

    print(f"Testing Registration with {test_email}...")
    try:
        res = requests.post(
            f"{base_url}/auth/register",
            json={
                "email": test_email,
                "password": test_password,
                "full_name": "E2E Test User",
            },
        )
        res.raise_for_status()
        print("✅ Registration Passed")
    except requests.RequestException as e:
        print(f"❌ Registration Failed: {e}")
        if "res" in locals():
            print(res.text)
        sys.exit(1)

    # 3. Login
    print("Testing Login...")
    try:
        res = requests.post(
            f"{base_url}/auth/login",
            data={"username": test_email, "password": test_password},
        )
        res.raise_for_status()
        token = res.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ Login Passed")
    except requests.RequestException as e:
        print(f"❌ Login Failed: {e}")
        sys.exit(1)

    # 4. Get Current User
    print("Testing Get Me...")
    try:
        res = requests.get(f"{base_url}/users/me", headers=headers)
        res.raise_for_status()
        print("✅ Get Current User Passed")
    except requests.RequestException as e:
        print(f"❌ Get Current User Failed: {e}")
        sys.exit(1)

    # 4b. Hunt Rules save (G1)
    print("Testing Hunt Rules save...")
    try:
        prefs_payload = {
            "keywords": ["python", "fastapi", "freelance"],
            "exclude_keywords": ["full-time"],
            "min_budget": None,
            "max_budget": None,
            "sources": [],
            "match_threshold": 0.35,
            "notification_channels": ["email"],
            "digest_mode": True,
            "freelance_focus": True,
            "location": "Remote",
            "timezone": "UTC",
            "digest_days": ["mon", "tue", "wed", "thu", "fri"],
            "digest_time_local": "09:00",
            "max_per_digest": 5,
            "notes": None,
            "alert_email": test_email,
        }
        res = requests.put(
            f"{base_url}/preferences/me", headers=headers, json=prefs_payload
        )
        res.raise_for_status()
        saved = res.json()
        if saved.get("freelance_focus") is not True:
            raise RuntimeError("freelance_focus not persisted")
        if saved.get("digest_mode") is not True:
            raise RuntimeError("digest_mode not persisted")
        print("✅ Hunt Rules Save Passed")
    except (requests.RequestException, RuntimeError) as e:
        print(f"❌ Hunt Rules Save Failed: {e}")
        if "res" in locals():
            print(getattr(res, "text", ""))
        sys.exit(1)

    # 4c. Auth findings (G1 / Open original fields)
    print("Testing Auth Findings...")
    try:
        res = requests.get(
            f"{base_url}/preferences/findings",
            headers=headers,
            params={"limit": 5, "freelance_focus": "true"},
        )
        res.raise_for_status()
        findings = res.json()
        if "items" not in findings:
            raise RuntimeError("findings missing items")
        for item in findings.get("items") or []:
            if not (item.get("apply_url") or item.get("url")):
                raise RuntimeError(f"finding missing original URL: {item}")
        print("✅ Auth Findings Passed")
    except (requests.RequestException, RuntimeError) as e:
        print(f"❌ Auth Findings Failed: {e}")
        sys.exit(1)

    # 5. Forgot password accepts the request without revealing whether the mailbox exists
    print("Testing Forgot Password...")
    try:
        res = requests.post(
            f"{base_url}/auth/forgot-password", json={"email": test_email}
        )
        res.raise_for_status()
        print("✅ Forgot Password Passed")
    except requests.RequestException as e:
        print(f"❌ Forgot Password Failed: {e}")
        sys.exit(1)

    # 6. Public job list
    print("Testing Job List...")
    try:
        res = requests.get(f"{base_url}/jobs", params={"limit": 5})
        res.raise_for_status()
        print("✅ Job List Passed")
    except requests.RequestException as e:
        print(f"❌ Job List Failed: {e}")
        sys.exit(1)

    # 7. Roadmap vote persists
    print("Testing Roadmap Vote...")
    try:
        voter = f"e2e-{get_random_string(12)}"
        res = requests.post(
            f"{base_url}/roadmap/votes",
            json={"feature_key": "ai-proposals", "voter_id": voter},
        )
        res.raise_for_status()
        again = requests.post(
            f"{base_url}/roadmap/votes",
            json={"feature_key": "ai-proposals", "voter_id": voter},
        )
        again.raise_for_status()
        if res.json().get("votes") != again.json().get("votes"):
            raise RuntimeError("second vote changed the count")
        print("✅ Roadmap Vote Passed")
    except (requests.RequestException, RuntimeError) as e:
        print(f"❌ Roadmap Vote Failed: {e}")
        sys.exit(1)

    # 8. Exit survey
    print("Testing Exit Survey...")
    try:
        res = requests.post(
            f"{base_url}/feedback/cancellation",
            json={"reason": "other", "details": "e2e"},
        )
        if res.status_code != 202:
            raise RuntimeError(res.text)
        print("✅ Exit Survey Passed")
    except (requests.RequestException, RuntimeError) as e:
        print(f"❌ Exit Survey Failed: {e}")
        sys.exit(1)

    # 9. Billing plans (subscribe itself needs live Stripe keys)
    print("Testing Billing Plans...")
    try:
        res = requests.get(f"{base_url}/billing/plans")
        res.raise_for_status()
        print("✅ Billing Plans Passed")
    except requests.RequestException as e:
        print(f"❌ Billing Plans Failed: {e}")
        sys.exit(1)

    # 10. Delete the account created above
    print("Testing Account Delete...")
    try:
        res = requests.delete(f"{base_url}/users/me", headers=headers)
        if res.status_code != 204:
            raise RuntimeError(res.text)
        print("✅ Account Delete Passed")
    except (requests.RequestException, RuntimeError) as e:
        print(f"❌ Account Delete Failed: {e}")
        sys.exit(1)

    print(
        "\n🎉 API checks passed (health, register, login, Hunt Rules, findings, jobs, roadmap, exit survey, billing plans, delete)."
    )
    print(
        "Subscribe, SerpAPI scrape, and digest delivery still need a host with keys and Celery beat."
    )


if __name__ == "__main__":
    main()
