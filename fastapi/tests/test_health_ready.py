"""Health readiness returns truthful statuses without leaking secrets."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.mark.asyncio
async def test_liveness_alive() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health/live")
    assert res.status_code == 200
    assert res.json()["status"] == "alive"
    assert "X-Request-Id" in res.headers


@pytest.mark.asyncio
async def test_ready_unavailable_when_db_down() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    with patch(
        "app.api.v1.health._check_database",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/health/ready")
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "unavailable"
    assert str(body["checks"]["database"]).startswith("down:")
    # No connection strings in payload
    dumped = str(body)
    assert "postgres://" not in dumped
    assert "redis://" not in dumped


@pytest.mark.asyncio
async def test_error_envelope_includes_request_id() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/users/me",
            headers={"X-Request-Id": "audit-req-123"},
        )
    assert res.status_code in {401, 403}
    body = res.json()
    assert "detail" in body
    assert body.get("request_id") == "audit-req-123"
    assert body.get("code")
    assert res.headers.get("X-Request-Id") == "audit-req-123"
