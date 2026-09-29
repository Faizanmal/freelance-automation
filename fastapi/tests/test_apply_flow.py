import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from backend.application.services.apply_service import ApplyError, ApplyService
from backend.application.services.proposal_draft import (
    ProposalDraftService,
    extract_apply_email,
    submit_mode_for_source,
)


class ProposalDraftShapeTests(unittest.IsolatedAsyncioTestCase):
    async def test_template_form_fields_for_all_sources(self) -> None:
        user = SimpleNamespace(full_name="Ada", email="ada@example.com")
        prefs = SimpleNamespace(
            keywords=["python", "fastapi"],
            notes="5 years backend",
            min_budget=200,
            max_budget=800,
        )
        job = SimpleNamespace(
            id=11,
            source_name="freelancer",
            source_id="12345",
            title="Build FastAPI service",
            description="Need a FastAPI microservice with auth.",
            url="https://www.freelancer.com/projects/12345",
            company="Client",
            budget_min=300,
            budget_max=700,
            analysis_summary="Backend API work",
            enrichment={"summary": "API + auth"},
        )
        with patch("backend.application.services.proposal_draft.any_llm_configured", return_value=False):
            result = await ProposalDraftService().draft(user=user, preferences=prefs, job=job)

        fields = result["form_fields"]
        assert isinstance(fields, dict)
        self.assertEqual(fields["submit_mode"], "api_bid")
        self.assertEqual(fields["source_id"], "12345")
        self.assertIn("FastAPI", fields["proposal"])
        self.assertEqual(fields["bid_amount"], 500.0)
        self.assertEqual(result["provider"], "template")

    def test_submit_modes(self) -> None:
        self.assertEqual(submit_mode_for_source("freelancer"), "api_bid")
        self.assertEqual(submit_mode_for_source("upwork"), "api_proposal")
        self.assertEqual(submit_mode_for_source("remoteok"), "email_apply")
        self.assertEqual(submit_mode_for_source("himalayas"), "email_apply")
        self.assertEqual(submit_mode_for_source("jobicy"), "email_apply")
        self.assertEqual(submit_mode_for_source("unknown"), "unsupported")

    def test_extract_apply_email(self) -> None:
        job = SimpleNamespace(
            url="https://example.com/jobs/1",
            description="Apply at hiring@acme.test with resume.",
        )
        self.assertEqual(extract_apply_email(job), "hiring@acme.test")


class ApplyServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_freelancer_submit_calls_place_bid(self) -> None:
        session = SimpleNamespace(add=lambda *_: None, flush=AsyncMock())
        user = SimpleNamespace(id="u1", email="ada@example.com")
        job = SimpleNamespace(
            id=9,
            source_name="freelancer",
            source_id="555",
            title="API job",
            url="https://www.freelancer.com/projects/555",
            description="desc",
        )
        service = ApplyService(session)  # type: ignore[arg-type]
        with patch(
            "backend.application.services.apply_service.freelancer_api.place_bid",
            new=AsyncMock(return_value={"id": 99}),
        ) as place_bid:
            result = await service.submit(
                user=user,
                job=job,
                form_fields={
                    "proposal": "Hello, I can help.",
                    "bid_amount": 250,
                    "currency": "USD",
                    "delivery_days": 10,
                    "milestone_percentage": 100,
                },
                confirm=True,
            )
        place_bid.assert_awaited_once()
        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["external_id"], "99")

    async def test_confirm_required(self) -> None:
        session = SimpleNamespace(add=lambda *_: None, flush=AsyncMock())
        service = ApplyService(session)  # type: ignore[arg-type]
        with self.assertRaises(ApplyError) as ctx:
            await service.submit(
                user=SimpleNamespace(id="u1", email="a@b.c"),
                job=SimpleNamespace(id=1, source_name="freelancer", source_id="1", title="t", url="u", description="d"),
                form_fields={"proposal": "hi", "bid_amount": 10},
                confirm=False,
            )
        self.assertEqual(ctx.exception.code, "confirm_required")

    async def test_upwork_submit_raises_unavailable(self) -> None:
        session = SimpleNamespace(add=lambda *_: None, flush=AsyncMock())
        user = SimpleNamespace(id="u1", email="ada@example.com")
        job = SimpleNamespace(
            id=9,
            source_name="upwork",
            source_id="555",
            title="API job",
            url="https://www.upwork.com/jobs/555",
            description="desc",
        )
        service = ApplyService(session)  # type: ignore[arg-type]
        with patch("backend.application.services.apply_service.upwork_api.upwork_configured", return_value=True), self.assertRaises(ApplyError) as ctx:
            await service.submit(
                user=user,
                job=job,
                form_fields={"proposal": "Hello"},
                confirm=True,
            )
        self.assertEqual(ctx.exception.code, "upwork_submit_unavailable")

    async def test_email_submit_success(self) -> None:
        session = SimpleNamespace(add=lambda *_: None, flush=AsyncMock())
        user = SimpleNamespace(id="u1", email="ada@example.com")
        job = SimpleNamespace(
            id=9,
            source_name="remoteok",
            source_id="555",
            title="API job",
            url="https://remoteok.com/555",
            description="Apply at hiring@example.com",
        )
        service = ApplyService(session)  # type: ignore[arg-type]
        with patch.dict("os.environ", {
            "EMAIL_SMTP_HOST": "smtp.test",
            "EMAIL_USERNAME": "testuser",
            "EMAIL_PASSWORD": "testpassword",
            "EMAIL_FROM": "bot@test.com"
        }), patch("backend.application.services.apply_service.smtplib.SMTP") as mock_smtp:
            result = await service.submit(
                user=user,
                job=job,
                form_fields={"proposal": "Hello"},
                confirm=True,
            )
        mock_smtp.assert_called_once()
        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["result"]["channel"], "email")
        self.assertEqual(result["external_id"], "hiring@example.com")

    async def test_freelancer_missing_bid_amount(self) -> None:
        session = SimpleNamespace(add=lambda *_: None, flush=AsyncMock())
        user = SimpleNamespace(id="u1", email="ada@example.com")
        job = SimpleNamespace(
            id=9,
            source_name="freelancer",
            source_id="555",
            title="API job",
            url="https://www.freelancer.com/projects/555",
            description="desc",
        )
        service = ApplyService(session)  # type: ignore[arg-type]
        with self.assertRaises(ApplyError) as ctx:
            await service.submit(
                user=user,
                job=job,
                form_fields={"proposal": "Hello"},
                confirm=True,
            )
        self.assertEqual(ctx.exception.code, "bid_amount_required")


if __name__ == "__main__":
    unittest.main()
