from __future__ import annotations

import pytest

from app.integrations.hn_hiring import (
    _clean_html,
    _parse_hn_header,
    fetch_hn_hiring_jobs,
)


def test_clean_html():
    raw = "<p>Acme Corp | Senior React Engineer | Remote | Contract</p><p>We are looking for someone with &gt;5 years of experience.<br>Pay is $100&#x2F;hr.</p>"
    cleaned = _clean_html(raw)
    assert "Acme Corp | Senior React Engineer | Remote | Contract" in cleaned
    assert "Pay is $100/hr." in cleaned
    assert "<p>" not in cleaned
    assert "<br>" not in cleaned


def test_parse_hn_header():
    text = "Supabase | Frontend Contractor | Remote | Contract\nWe need help building auth dashboards."
    title, company, tags = _parse_hn_header(text)
    assert title == "Supabase — Frontend Contractor"
    assert company == "Supabase"
    assert "Remote" in tags
    assert "Contract" in tags


@pytest.mark.asyncio
async def test_fetch_hn_hiring_mock(monkeypatch):
    import httpx

    fake_user = {"submitted": [101, 102]}
    fake_story_1 = {
        "id": 101,
        "title": "Ask HN: Freelancer? Seeking freelancer? (November 2026)",
        "kids": [201, 202, 203],
    }
    fake_comments = {
        201: {
            "id": 201,
            "by": "client_dan",
            "time": 1730500000,
            "text": "<p>SEEKING FREELANCER | CloudOps | Senior DevOps | Remote</p><p>We need Terraform and AWS help for 3 months.</p>",
        },
        202: {
            "id": 202,
            "by": "freelancer_bob",
            "time": 1730500000,
            "text": "<p>SEEKING WORK | Fullstack Dev</p><p>I am available for hire.</p>",
        },
        203: {
            "id": 203,
            "by": "client_sue",
            "time": 1730500000,
            "text": "<p>FinTech Inc | Python &amp; FastAPI Lead | Remote | Contract</p><p>Looking for a contract engineer to build integrations.</p>",
        },
    }

    class MockResponse:
        def __init__(self, data, status_code=200):
            self._data = data
            self.status_code = status_code

        def json(self):
            return self._data

        def raise_for_status(self):
            pass

    async def mock_get(self, url, *args, **kwargs):
        if "whoishiring.json" in url:
            return MockResponse(fake_user)
        for sid in (101, 102):
            if f"/item/{sid}.json" in url:
                return MockResponse(fake_story_1)
        for cid, comment in fake_comments.items():
            if f"/item/{cid}.json" in url:
                return MockResponse(comment)
        return MockResponse({}, status_code=404)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    candidates = await fetch_hn_hiring_jobs(limit=10)
    assert len(candidates) == 2  # comment 202 (SEEKING WORK) must be skipped!
    assert candidates[0].source_name == "hn_hiring"
    assert "CloudOps" in candidates[0].title or "CloudOps" in candidates[0].description
    assert candidates[0].url == "https://news.ycombinator.com/item?id=201"
    assert candidates[1].company == "FinTech Inc"

