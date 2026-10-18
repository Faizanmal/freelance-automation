"""Ping the public health endpoints. Exits 0 when UPTIME_URL is unset so local runs stay quiet."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def _get(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=15) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, body


def main() -> int:
    base = os.environ.get("UPTIME_URL", "").rstrip("/")
    if not base:
        print(
            "UPTIME_URL is not set. Set it to the public origin, for example https://app.example.com"
        )
        return 0

    live_url = f"{base}/health/live"
    ready_url = f"{base}/health/ready"
    try:
        live_status, _ = _get(live_url)
        ready_status, ready_body = _get(ready_url)
    except urllib.error.URLError as exc:
        print(f"Unhealthy: {base} ({exc})")
        return 1

    if live_status != 200 or ready_status != 200:
        print(f"Unhealthy: live={live_status} ready={ready_status}")
        return 1

    try:
        ready = json.loads(ready_body)
    except json.JSONDecodeError:
        print(f"Unhealthy: {ready_url} did not return JSON")
        return 1

    if ready.get("status") != "ok":
        print(f"Unhealthy: {ready}")
        return 1

    print(f"Healthy: {live_url} and {ready_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
