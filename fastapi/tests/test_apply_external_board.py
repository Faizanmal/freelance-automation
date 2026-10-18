"""Remaining: public boards without mailto use external_apply (prepared)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from backend.application.services.apply_service import ApplyService


class ExternalBoardApplyTests(unittest.IsolatedAsyncioTestCase):
    async def test_board_without_email_prepares_external(self) -> None:
        session = SimpleNamespace(add=lambda *_: None, flush=AsyncMock())
        user = SimpleNamespace(id="u1", email="ada@example.com")
        job = SimpleNamespace(
            id=9,
            source_name="remoteok",
            source_id="555",
            title="API job",
            url="https://remoteok.com/remote-jobs/555",
            description="Apply on the listing page. No email here.",
        )
        service = ApplyService(session)  # type: ignore[arg-type]
        result = await service.submit(
            user=user,
            job=job,
            form_fields={"proposal": "Hello, interested in this role."},
            confirm=True,
        )
        self.assertEqual(result["status"], "prepared")
        self.assertEqual(result["submit_mode"], "external_apply")
        self.assertEqual(result["apply_url"], job.url)


if __name__ == "__main__":
    unittest.main()
