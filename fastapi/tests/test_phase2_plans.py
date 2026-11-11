from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.ingestion.sources import COMMERCIAL_FREE_SOURCES, SOURCE_REGISTRY
from app.main import app
from backend.application.services.lead_findings import LeadFindingsService
from backend.application.services.match_feedback import MatchFeedbackService
from backend.application.services.matching import JobMatch
from backend.application.services.notification_service import (
    CustomWebhookAdapter,
    NotificationChannel,
    NotificationEnvelope,
    NotificationPriority,
)
from database.models.job import JobRecord
from database.models.lead_action import UserLeadAction
from database.models.user import User


def test_sources_registration_includes_ats():
    assert "greenhouse" in SOURCE_REGISTRY
    assert "lever" in SOURCE_REGISTRY
    assert "ashby" in SOURCE_REGISTRY
    assert "ats_direct" in SOURCE_REGISTRY
    assert "greenhouse" in COMMERCIAL_FREE_SOURCES
    assert "lever" in COMMERCIAL_FREE_SOURCES
    assert "ashby" in COMMERCIAL_FREE_SOURCES
    assert "ats_direct" in COMMERCIAL_FREE_SOURCES


@pytest.mark.asyncio
async def test_match_feedback_affinity_profile():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    session = AsyncMock()
    action_save = SimpleNamespace(status="save", job_id=901)
    job_save = SimpleNamespace(id=901, enrichment={"skills": ["react", "typescript"]}, tags=[])

    action_skip = SimpleNamespace(status="skip", job_id=902)
    job_skip = SimpleNamespace(id=902, enrichment={"skills": ["wordpress", "php"]}, tags=[])

    mock_result = MagicMock()
    mock_result.all.return_value = [
        (action_save, job_save),
        (action_skip, job_skip),
    ]
    session.execute.return_value = mock_result

    feedback_service = MatchFeedbackService(session)
    profile = await feedback_service.get_affinity_profile("user-aff-1")

    assert profile["total_actions"] == 2
    assert profile["saved_count"] == 1
    assert profile["skipped_count"] == 1
    assert profile["learning_active"] is True
    pos_skills = [p["skill"] for p in profile["positive_skills"]]
    assert "react" in pos_skills
    neg_skills = [n["skill"] for n in profile["negative_skills"]]
    assert "wordpress" in neg_skills
    assert "Boosting: react" in profile["summary"]


@pytest.mark.asyncio
async def test_lead_finding_smart_match_extraction():
    job = JobRecord(
        id=999,
        source_name="ats_direct",
        source_id="ats-999",
        title="Full Stack Engineer",
        description="Contract role for React engineer",
        url="https://company.com/job",
    )
    match = JobMatch(
        job=job,
        score=0.85,
        matched_keywords=["react"],
        reasons=["keyword match", "saved-skill boost: react, typescript"],
        freshness_score=0.9,
        client_quality_score=0.8,
        red_flags=[],
    )

    findings_service = LeadFindingsService()
    finding = findings_service._from_match(match, freelance_focus=True)

    assert finding.smart_match is not None
    assert finding.smart_match["is_boosted"] is True
    assert "saved-skill boost" in finding.smart_match["reason"]

    as_dict = findings_service.to_dict(finding)
    assert as_dict["smart_match"]["is_boosted"] is True


@pytest.mark.asyncio
async def test_custom_webhook_adapter(monkeypatch):
    adapter = CustomWebhookAdapter(endpoint="https://hooks.zapier.com/test")

    captured_url = None
    captured_payload = None

    def mock_send_sync(endpoint, payload):
        nonlocal captured_url, captured_payload
        captured_url = endpoint
        captured_payload = payload
        return "200"

    monkeypatch.setattr(adapter, "_send_sync", mock_send_sync)

    envelope = NotificationEnvelope(
        id="notif-test-1",
        user_id="user-123",
        title="High Match Lead Alert",
        body="Found React Contract: $80/hr",
        channels=[NotificationChannel.WEBHOOK],
        priority=NotificationPriority.HIGH,
        digest=False,
        ai_summary=None,
        actions=[],
        destinations={"custom_webhook_url": "https://hooks.zapier.com/custom"},
        metadata={"job_id": 999, "score": 0.92},
    )

    result = await adapter.send(envelope)
    assert result.delivered is True
    assert captured_url == "https://hooks.zapier.com/custom"
    assert b"High Match Lead Alert" in captured_payload
    assert b"lead.alert" in captured_payload


@pytest.mark.asyncio
async def test_endpoint_test_webhook_validation():
    from unittest.mock import AsyncMock
    from fastapi import HTTPException
    from app.api.v1.preferences import TestWebhookPayload, test_user_webhook
    from types import SimpleNamespace

    user = SimpleNamespace(id="u-1", email="test@test.com")
    session = AsyncMock()

    # Invalid URL scheme
    with pytest.raises(HTTPException) as exc_info:
        await test_user_webhook(
            TestWebhookPayload(webhook_url="ftp://invalid.com"),
            user=user,
            session=session,
        )
    assert exc_info.value.status_code == 400
    assert "http://" in exc_info.value.detail

    # Blocked SSRF metadata host
    with pytest.raises(HTTPException) as exc_info:
        await test_user_webhook(
            TestWebhookPayload(webhook_url="http://169.254.169.254/latest/meta-data"),
            user=user,
            session=session,
        )
    assert exc_info.value.status_code == 400
    assert "Forbidden" in exc_info.value.detail
