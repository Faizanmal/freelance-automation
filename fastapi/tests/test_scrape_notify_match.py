"""Instant match notify must use MatchingService.score_job (not removed APIs)."""

from __future__ import annotations

import inspect

from backend.application.services.scrape_service import ScrapeService


def test_notify_users_uses_score_job_not_calculate_match() -> None:
    source = inspect.getsource(ScrapeService._notify_users_of_new_jobs)
    assert "calculate_match" not in source
    assert "score_job" in source
    assert "if match is None" in source
