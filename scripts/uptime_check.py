"""Ping public health endpoints. Fail closed when UPTIME_URL is missing or unhealthy."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def _get(url: str, timeout: float = 15.0) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, body


def main() -> int:
    base = os.environ.get("UPTIME_URL", "").rstrip("/")
    if not base:
        print(
            "UPTIME_URL is not set. Set it to the public API origin "
            "(for example https://api.example.com/api/v1) or a full "
            "/health/live URL. Refusing to report healthy."
        )
        return 1

    # Defensively normalize if the user passed a full endpoint URL
    if base.endswith("/health/live"):
        base = base[: -len("/health/live")].rstrip("/")
    elif base.endswith("/health/ready"):
        base = base[: -len("/health/ready")].rstrip("/")
    elif base.endswith("/health"):
        base = base[: -len("/health")].rstrip("/")

    live_url = f"{base}/health/live"
    ready_url = f"{base}/health/ready"
    try:
        live_status, _ = _get(live_url)
        ready_status, ready_body = _get(ready_url)
    except urllib.error.HTTPError as exc:
        print(f"Unhealthy: HTTP {exc.code} for {exc.url}")
        return 1
    except urllib.error.URLError as exc:
        print(f"Unhealthy: {base} ({exc})")
        return 1
    except TimeoutError:
        print(f"Unhealthy: timeout contacting {base}")
        return 1

    if live_status != 200 or ready_status != 200:
        print(f"Unhealthy: live={live_status} ready={ready_status}")
        return 1

    try:
        ready = json.loads(ready_body)
    except json.JSONDecodeError:
        print(f"Unhealthy: {ready_url} did not return JSON")
        return 1

    status = ready.get("status")
    if status not in {"ok", "degraded"}:
        print(f"Unhealthy: unexpected ready status {ready!r}")
        return 1

    # Degraded is still "up" for liveness ping; log clearly.
    print(f"Healthy ({status}): {live_url} and {ready_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
