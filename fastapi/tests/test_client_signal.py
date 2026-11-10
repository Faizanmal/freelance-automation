import unittest

from backend.application.services.client_signal import detect_client_signal
from backend.application.services.proposal_draft import build_outreach_links, ProposalDraftService
from database.models.job import JobRecord
from database.models.preference import UserPreferences
from database.models.user import User


class ClientSignalTests(unittest.TestCase):
    def test_detects_staffing_agency_by_keyword(self) -> None:
        signal = detect_client_signal(
            title="Senior Python Engineer",
            description="Our client is looking for an experienced FastAPI consultant on behalf of a financial services firm.",
            company="Confidential Client",
            source_name="serpapi_jobs",
        )
        self.assertTrue(signal.is_agency)
        self.assertEqual(signal.poster_type, "agency_recruiter")
        self.assertEqual(signal.poster_badge, "agency")
        self.assertIn("Mentions staffing intermediary", signal.reasons[0])

    def test_detects_staffing_agency_by_company_name(self) -> None:
        signal = detect_client_signal(
            title="React Developer",
            description="Building new features for a high growth app.",
            company="CyberCoders",
            source_name="remoteok",
        )
        self.assertTrue(signal.is_agency)
        self.assertEqual(signal.poster_type, "agency_recruiter")

    def test_detects_direct_founder_by_keyword(self) -> None:
        signal = detect_client_signal(
            title="Full-Stack Developer",
            description="I'm the founder of an AI startup. Looking for someone to work directly with me to build our v1.",
            company="SignalTech",
            source_name="serpapi_freelance",
        )
        self.assertFalse(signal.is_agency)
        self.assertEqual(signal.poster_type, "direct_founder")
        self.assertEqual(signal.poster_badge, "founder")
        self.assertGreaterEqual(signal.score, 90)

    def test_detects_direct_founder_from_hn_source(self) -> None:
        signal = detect_client_signal(
            title="Contract Backend Developer",
            description="Need Python/Postgres help for 2 months.",
            company="SmallCo",
            source_name="hn_hiring",
        )
        self.assertFalse(signal.is_agency)
        self.assertEqual(signal.poster_type, "direct_founder")

    def test_detects_high_urgency_signal(self) -> None:
        signal = detect_client_signal(
            title="DevOps Contractor",
            description="Immediate start needed! Looking for someone who can start this week to fix our Kubernetes cluster.",
            company="Acme Corp",
            source_name="serpapi_jobs",
        )
        self.assertEqual(signal.urgency, "high")
        self.assertIsNotNone(signal.urgency_label)


class OutreachLinksAndFollowupTests(unittest.IsolatedAsyncioTestCase):
    def test_build_outreach_links(self) -> None:
        links = build_outreach_links(
            to_email="hiring@example.com",
            subject="Contract inquiry: Python Dev",
            body="Hi, I saw your post and can help.",
        )
        self.assertIn("https://mail.google.com/mail/?", links["gmail"])
        self.assertIn("to=hiring%40example.com", links["gmail"])
        self.assertIn("mailto:hiring@example.com?subject=", links["mailto"])

    async def test_proposal_draft_initial_and_followup(self) -> None:
        user = User(
            id="test-user-outreach-1",
            email="developer@example.com",
            full_name="Alex Dev",
            hashed_password="hash",
        )
        prefs = UserPreferences(
            user_id=user.id,
            keywords=["python", "fastapi"],
            exclude_keywords=[],
            sources=[],
            notification_channels=["email"],
        )
        job = JobRecord(
            id=999,
            source_name="remoteok",
            source_id="job-999",
            canonical_id="remoteok::job-999",
            title="FastAPI Contractor",
            description="Looking for a Python dev. Apply via mailto:jobs@fastcorp.io.",
            url="https://remoteok.com/remote-jobs/999",
            company="FastCorp",
        )

        service = ProposalDraftService()
        initial_res = await service.draft(user=user, preferences=prefs, job=job, kind="initial")
        self.assertEqual(initial_res["kind"], "initial")
        self.assertIn("Alex Dev", str(initial_res["draft"]))
        self.assertIn("jobs@fastcorp.io", str(initial_res["apply_email"]))
        self.assertIn("gmail", initial_res["outreach_links"])
        self.assertIn("mailto", initial_res["outreach_links"])

        followup_res = await service.draft(user=user, preferences=prefs, job=job, kind="followup")
        self.assertEqual(followup_res["kind"], "followup")
        self.assertIn("following up briefly", str(followup_res["draft"]).lower())
        self.assertIn("Following up: FastAPI Contractor", str(followup_res["email_subject"]))


if __name__ == "__main__":
    unittest.main()

