from __future__ import annotations

import httpx
import pytest

from app.ingestion.direct_ats import (
    AshbySource,
    DirectATSSource,
    GreenhouseSource,
    LeverSource,
)


@pytest.mark.asyncio
async def test_greenhouse_source_parsing(monkeypatch):
    source = GreenhouseSource(boards=("testco",))

    mock_response = {
        "jobs": [
            {
                "id": 101,
                "title": "Senior React Developer (Contract)",
                "updated_at": "2026-03-01T10:00:00Z",
                "absolute_url": "https://boards.greenhouse.io/testco/jobs/101",
                "location": {"name": "Remote, Global"},
                "departments": [{"name": "Frontend"}],
                "content": "<p>We are looking for a contract frontend specialist.</p>",
            },
            {
                "id": 102,
                "title": "Permanent HR Manager",
                "updated_at": "2026-03-01T10:00:00Z",
                "absolute_url": "https://boards.greenhouse.io/testco/jobs/102",
                "location": {"name": "New York, NY"},
                "departments": [{"name": "People"}],
                "content": "<p>Full-time HR manager role.</p>",
            },
        ]
    }

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def get(self, url):
            request = httpx.Request("GET", url)
            return httpx.Response(200, json=mock_response, request=request)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: MockClient())

    candidates = await source.fetch(limit=10)
    assert len(candidates) == 1
    assert candidates[0].title == "Senior React Developer (Contract)"
    assert candidates[0].source_name == "greenhouse"
    assert candidates[0].company == "Testco"
    assert "contract frontend specialist" in candidates[0].description
    assert candidates[0].metadata["location"] == "Remote, Global"
    assert candidates[0].metadata["ats"] == "greenhouse"


@pytest.mark.asyncio
async def test_lever_source_parsing(monkeypatch):
    source = LeverSource(companies=("leverco",))

    mock_response = [
        {
            "id": "lev-101",
            "text": "Full Stack Engineer - Freelance",
            "hostedUrl": "https://jobs.lever.co/leverco/lev-101",
            "createdAt": 1700000000000,
            "categories": {
                "commitment": "Contract",
                "department": "Engineering",
                "team": "Platform",
                "location": "Remote",
            },
            "description": "<p>We need a freelance engineer for 3 months.</p>",
            "descriptionPlain": "We need a freelance engineer for 3 months.",
        }
    ]

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def get(self, url):
            request = httpx.Request("GET", url)
            return httpx.Response(200, json=mock_response, request=request)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: MockClient())

    candidates = await source.fetch(limit=10)
    assert len(candidates) == 1
    assert candidates[0].title == "Full Stack Engineer - Freelance"
    assert candidates[0].source_name == "lever"
    assert candidates[0].company == "Leverco"
    assert candidates[0].metadata["commitment"] == "Contract"


@pytest.mark.asyncio
async def test_ashby_source_parsing(monkeypatch):
    source = AshbySource(organizations=("ashbyorg",))

    mock_response = {
        "jobs": [
            {
                "id": "ash-101",
                "title": "Python Automation Consultant",
                "department": "Infrastructure",
                "employmentType": "Contract",
                "location": "Worldwide",
                "jobUrl": "https://jobs.ashbyhq.com/ashbyorg/ash-101",
                "publishedAt": "2026-03-02T12:00:00Z",
                "descriptionHtml": "<p>Contract consulting role for Python automation.</p>",
            }
        ]
    }

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def get(self, url):
            request = httpx.Request("GET", url)
            return httpx.Response(200, json=mock_response, request=request)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: MockClient())

    candidates = await source.fetch(limit=10)
    assert len(candidates) == 1
    assert candidates[0].title == "Python Automation Consultant"
    assert candidates[0].source_name == "ashby"
    assert candidates[0].metadata["employment_type"] == "Contract"


@pytest.mark.asyncio
async def test_direct_ats_unified(monkeypatch):
    ats = DirectATSSource()

    async def mock_gh_fetch(*args, **kwargs):
        from backend.application.services.duplicate_detection import JobCandidate
        return [JobCandidate(source_name="greenhouse", source_id="1", title="GH Job", description="desc", url="http://gh.com", metadata={})]

    async def mock_lever_fetch(*args, **kwargs):
        from backend.application.services.duplicate_detection import JobCandidate
        return [JobCandidate(source_name="lever", source_id="2", title="Lever Job", description="desc", url="http://lev.com", metadata={})]

    async def mock_ashby_fetch(*args, **kwargs):
        from backend.application.services.duplicate_detection import JobCandidate
        return [JobCandidate(source_name="ashby", source_id="3", title="Ashby Job", description="desc", url="http://ash.com", metadata={})]

    monkeypatch.setattr(ats.greenhouse, "fetch", mock_gh_fetch)
    monkeypatch.setattr(ats.lever, "fetch", mock_lever_fetch)
    monkeypatch.setattr(ats.ashby, "fetch", mock_ashby_fetch)

    candidates = await ats.fetch(limit=10)
    assert len(candidates) == 3
    assert all(c.source_name == "ats_direct" for c in candidates)
    assert candidates[0].metadata["underlying_source"] == "greenhouse"
