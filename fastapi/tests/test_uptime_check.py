"""Uptime checker must fail closed on missing URL / bad responses."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

import scripts.uptime_check as uptime_check


def test_missing_uptime_url_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UPTIME_URL", raising=False)
    assert uptime_check.main() == 1


def test_non_200_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UPTIME_URL", "https://api.example.com/api/v1")

    def fake_get(url: str, timeout: float = 15.0):
        if url.endswith("/live"):
            return 500, "nope"
        return 200, json.dumps({"status": "ok"})

    with patch.object(uptime_check, "_get", side_effect=fake_get):
        assert uptime_check.main() == 1


def test_invalid_json_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UPTIME_URL", "https://api.example.com/api/v1")

    def fake_get(url: str, timeout: float = 15.0):
        if url.endswith("/live"):
            return 200, '{"status":"alive"}'
        return 200, "not-json"

    with patch.object(uptime_check, "_get", side_effect=fake_get):
        assert uptime_check.main() == 1


def test_healthy_ok_and_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UPTIME_URL", "https://api.example.com/api/v1/health/live")

    def fake_get(url: str, timeout: float = 15.0):
        if url.endswith("/live"):
            return 200, '{"status":"alive"}'
        return 200, json.dumps({"status": "degraded", "checks": {"workers": "idle"}})

    with patch.object(uptime_check, "_get", side_effect=fake_get):
        assert uptime_check.main() == 0


def test_timeout_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UPTIME_URL", "https://api.example.com")
    with patch.object(uptime_check, "_get", side_effect=TimeoutError()):
        assert uptime_check.main() == 1
