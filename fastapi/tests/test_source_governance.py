"""Phase 05 — source governance, normalize, policy gate, reliability contracts."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.ingestion.contracts import classify_work_type
from app.ingestion.governance import (
    build_source_policy,
    governance_audit_summary,
    list_policies,
    set_operator_disabled,
)
from app.ingestion.normalize import (
    candidate_to_opportunity,
    enrich_candidate_classification,
    fingerprint_opportunity,
    inventory_quality_stats,
    opportunity_to_candidate,
    safe_http_url,
)
from app.ingestion.policy_gate import evaluate_source, filter_sources
from app.ingestion.reliability import (
    CIRCUIT_FAILURE_THRESHOLD,
    _LOCAL_CIRCUITS,
    _LOCAL_LEASES,
    _LOCAL_QUARANTINE,
    acquire_source_lease,
    circuit_is_open,
    quarantine_batch,
    record_source_failure,
    record_source_success,
    release_source_lease,
)
from app.ingestion.sources import RESTRICTED_SOURCES, SOURCE_REGISTRY, V1_DEFAULT_HUNTERS
from backend.application.services.duplicate_detection import JobCandidate

FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "permitted_opportunity_sample.jsonl"
)
FIXTURE_META = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "permitted_opportunity_sample_meta.json"
)


class TypedRegistryTests(unittest.TestCase):
    def test_every_adapter_has_policy(self) -> None:
        policies = {p.key: p for p in list_policies(include_disabled=True)}
        for key in SOURCE_REGISTRY:
            self.assertIn(key, policies)
            self.assertTrue(policies[key].attribution)

    def test_restricted_default_disabled(self) -> None:
        for key in RESTRICTED_SOURCES:
            policy = build_source_policy(key)
            self.assertEqual(policy.permission, "restricted")
            self.assertFalse(policy.enabled_by_default)

    def test_audit_summary_flags(self) -> None:
        summary = governance_audit_summary()
        self.assertTrue(summary["compliance"]["no_paywall_bypass"])
        self.assertTrue(summary["compliance"]["nulls_not_fabrications"])
        self.assertGreaterEqual(summary["adapter_count"], len(V1_DEFAULT_HUNTERS))


class PolicyGateTests(unittest.TestCase):
    def tearDown(self) -> None:
        for key in list(SOURCE_REGISTRY):
            set_operator_disabled(key, False)

    def test_restricted_blocked_without_opt_in(self) -> None:
        decision = evaluate_source("remotive")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "restricted_licensing")

    def test_operator_disable(self) -> None:
        set_operator_disabled("remoteok", True)
        decision = evaluate_source("remoteok")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "operator_disabled")

    def test_filter_drops_blocked(self) -> None:
        allowed, decisions = filter_sources(
            ["remoteok", "remotive", "unknown_xyz"],
            default=list(V1_DEFAULT_HUNTERS),
        )
        self.assertNotIn("remotive", allowed)
        self.assertNotIn("unknown_xyz", allowed)
        self.assertFalse(decisions["remotive"].allowed)


class NormalizeContractTests(unittest.TestCase):
    def test_rejects_javascript_url(self) -> None:
        self.assertIsNone(safe_http_url("javascript:alert(1)"))
        self.assertIsNone(safe_http_url("data:text/html,hi"))
        self.assertEqual(
            safe_http_url("https://example.com/job/1"),
            "https://example.com/job/1",
        )

    def test_nulls_not_fabricated_compensation(self) -> None:
        c = JobCandidate(
            source_name="remoteok",
            source_id="1",
            title="Engineer",
            description="Build APIs",
            url="https://example.com/1",
            company=None,
            budget_min=None,
            budget_max=None,
        )
        opp = candidate_to_opportunity(c)
        self.assertIsNone(opp.compensation_min)
        self.assertIsNone(opp.compensation_max)
        self.assertEqual(opp.compensation_period, "unknown")

    def test_work_type_classification_evidence(self) -> None:
        wt, evidence = classify_work_type(
            title="Freelance React developer",
            description="Need help with Next.js",
        )
        self.assertEqual(wt, "freelance")
        self.assertTrue(any("freelance" in e for e in evidence))

    def test_round_trip_preserves_ids(self) -> None:
        c = JobCandidate(
            source_name="arbeitnow",
            source_id="abc",
            title="Contract data engineer",
            description="6 month contract",
            url="https://example.com/abc",
            company="Acme",
            metadata={"tags": ["python"], "location": "Remote"},
        )
        enriched = enrich_candidate_classification(c)
        self.assertEqual(enriched.source_id, "abc")
        self.assertIn(
            enriched.metadata.get("work_type"),
            {"freelance", "contract", "full_time", "unknown"},
        )
        opp = candidate_to_opportunity(enriched)
        back = opportunity_to_candidate(opp)
        self.assertEqual(back.source_name, "arbeitnow")
        fp = fingerprint_opportunity(opp)
        self.assertEqual(len(fp), 64)


class ReliabilityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        _LOCAL_LEASES.clear()
        _LOCAL_CIRCUITS.clear()
        _LOCAL_QUARANTINE.clear()
        self._redis_patch = patch(
            "app.ingestion.reliability.get_redis",
            new_callable=AsyncMock,
            return_value=None,
        )
        self._redis_patch.start()

    def tearDown(self) -> None:
        self._redis_patch.stop()

    async def test_lease_exclusive(self) -> None:
        self.assertTrue(await acquire_source_lease("remoteok"))
        self.assertFalse(await acquire_source_lease("remoteok"))
        await release_source_lease("remoteok")
        self.assertTrue(await acquire_source_lease("remoteok"))

    async def test_circuit_opens_after_threshold(self) -> None:
        opened = False
        for i in range(CIRCUIT_FAILURE_THRESHOLD):
            opened = await record_source_failure("arbeitnow", error=f"e{i}")
        self.assertTrue(opened)
        self.assertTrue(await circuit_is_open("arbeitnow"))
        await record_source_success("arbeitnow")
        self.assertFalse(await circuit_is_open("arbeitnow"))

    async def test_quarantine_records(self) -> None:
        qid = await quarantine_batch(
            source_name="himalayas",
            reason="fetch_error",
            payload={"error": "timeout"},
        )
        self.assertTrue(qid)
        self.assertEqual(_LOCAL_QUARANTINE[0]["reason"], "fetch_error")


class FixtureCorpusTests(unittest.TestCase):
    def test_sample_size_at_least_200(self) -> None:
        self.assertTrue(FIXTURE.exists(), "fixture jsonl missing")
        lines = [
            ln for ln in FIXTURE.read_text(encoding="utf-8").splitlines() if ln.strip()
        ]
        self.assertGreaterEqual(len(lines), 200)
        meta = json.loads(FIXTURE_META.read_text(encoding="utf-8"))
        self.assertEqual(meta["count"], len(lines))
        self.assertTrue(meta["obtainable"])

    def test_work_type_precision_on_labeled_sample(self) -> None:
        rows = [
            json.loads(ln)
            for ln in FIXTURE.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        correct = 0
        for row in rows:
            # Methodology: title/description/tags only (no source prior) for
            # keyword classifier precision on labeled fixtures.
            pred, _ = classify_work_type(
                title=row["title"],
                description=row.get("description") or "",
                tags=row.get("skills") or [],
                source_hint=None,
            )
            if pred == row["work_type_label"]:
                correct += 1
        precision = correct / len(rows)
        # Labeled titles are keyword-aligned; expect high precision on this corpus.
        self.assertGreaterEqual(precision, 0.9)
        stats = inventory_quality_stats(
            [
                {
                    "url": r["canonical_url"],
                    "company": r["employer"],
                    "work_type": r["work_type_label"],
                    "is_expired": False,
                }
                for r in rows
            ]
        )
        self.assertEqual(stats["count"], 200)
        self.assertEqual(stats["url_coverage"], 1.0)

    def test_dedup_fingerprint_stable_and_distinct(self) -> None:
        rows = [
            json.loads(ln)
            for ln in FIXTURE.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ][:50]
        fps = set()
        for row in rows:
            c = JobCandidate(
                source_name=row["source_name"],
                source_id=row["source_id"],
                title=row["title"],
                description=row["description"],
                url=row["canonical_url"],
                company=row.get("employer"),
            )
            fp = fingerprint_opportunity(candidate_to_opportunity(c))
            self.assertNotIn(fp, fps)
            fps.add(fp)
        # Replay same row → same fingerprint (idempotent identity).
        first = rows[0]
        c1 = JobCandidate(
            source_name=first["source_name"],
            source_id=first["source_id"],
            title=first["title"],
            description=first["description"],
            url=first["canonical_url"],
            company=first.get("employer"),
        )
        self.assertEqual(
            fingerprint_opportunity(candidate_to_opportunity(c1)),
            fingerprint_opportunity(candidate_to_opportunity(c1)),
        )


class MalformedAdapterFixtureTests(unittest.TestCase):
    def test_missing_fields_become_nulls(self) -> None:
        c = JobCandidate(
            source_name="jobicy",
            source_id="x",
            title="",
            description="",
            url="",
        )
        opp = candidate_to_opportunity(c)
        self.assertEqual(opp.title, "Untitled")
        self.assertIsNone(opp.employer)
        self.assertEqual(opp.state, "unknown")  # no safe URL

    def test_partial_failure_stats(self) -> None:
        stats = inventory_quality_stats(
            [
                {"url": "https://a.com", "company": "A", "work_type": "freelance"},
                {"url": None, "company": None, "work_type": "unknown", "is_expired": True},
            ]
        )
        self.assertEqual(stats["count"], 2)
        self.assertEqual(stats["stale_marked_rate"], 0.5)


class GateFilterWithMockSettings(unittest.TestCase):
    def test_experimental_blocked(self) -> None:
        with patch("app.ingestion.policy_gate.get_settings") as gs:
            settings = gs.return_value
            settings.allow_browser_sources = False
            settings.allow_restricted_sources = False
            settings.scrape_source_list = None
            decision = evaluate_source("linkedin_browser")
            self.assertFalse(decision.allowed)


if __name__ == "__main__":
    unittest.main()
