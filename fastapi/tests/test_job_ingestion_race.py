"""Remaining: concurrent ingest uniqueness race is treated as skip/link."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.exc import IntegrityError

from backend.application.services.duplicate_detection import JobCandidate
from backend.application.services.job_ingestion import JobIngestionService


class JobIngestionRaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_integrity_error_returns_skipped_race_duplicate(self) -> None:
        session = AsyncMock()
        session.rollback = AsyncMock()
        existing = SimpleNamespace(id=99)

        repository = MagicMock()
        repository.get_by_source = AsyncMock(side_effect=[None, existing])
        repository.get_by_url = AsyncMock(return_value=None)
        repository.list_recent = AsyncMock(return_value=[])
        repository.create = AsyncMock(
            side_effect=IntegrityError("stmt", {}, Exception("dup"))
        )

        enrichment = MagicMock()
        enrichment.enrich = AsyncMock(
            return_value=SimpleNamespace(
                to_dict=dict,
                seniority=None,
                summary="ok",
                provider="template",
                skills=["python"],
            )
        )

        service = JobIngestionService(
            session,
            enrichment_service=enrichment,
        )
        service.repository = repository

        candidate = JobCandidate(
            source_name="remoteok",
            source_id="abc",
            title="Engineer",
            description="desc",
            url="https://example.com/j/1",
            company="Co",
        )
        result = await service.ingest(candidate)
        self.assertEqual(result["action"], "skipped")
        self.assertEqual(result["reason"], "race_duplicate")
        self.assertEqual(result["job_id"], 99)
        session.rollback.assert_awaited()


if __name__ == "__main__":
    unittest.main()
