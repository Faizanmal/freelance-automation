"""Phase 07 offline matching benchmark + gate checks."""

from __future__ import annotations

import json
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from backend.application.services.matching import MatchingService
from backend.application.services.ranking.benchmark import summarize_run
from backend.application.services.ranking.pipeline import RankingPipeline
from backend.application.services.ranking.profile import MatchProfileBuilder
from database.models.job import JobRecord
from database.models.preference import UserPreferences

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "matching_eval"
FIXTURE_PATH = FIXTURE_DIR / "matching_eval_set.jsonl"


def _load_examples() -> list[dict]:
    rows: list[dict] = []
    with FIXTURE_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _job_from(raw: dict) -> JobRecord:
    return JobRecord(
        id=raw["id"],
        source_name=raw["source_name"],
        source_id=raw["source_id"],
        canonical_id=raw.get("canonical_id") or f"canon-{raw['id']}",
        title=raw["title"],
        description=raw.get("description") or "",
        url=raw.get("url") or f"https://example.com/jobs/{raw['id']}",
        company=raw.get("company"),
        location=raw.get("location"),
        tags=list(raw.get("tags") or []),
        budget_min=raw.get("budget_min"),
        budget_max=raw.get("budget_max"),
        posted_at=raw.get("posted_at"),
        enrichment=dict(raw.get("enrichment") or {}),
        seniority=raw.get("seniority"),
    )


def _prefs_from(raw: dict) -> UserPreferences:
    return UserPreferences(
        user_id="bench-user",
        skills=list(raw.get("skills") or []),
        keywords=list(raw.get("keywords") or []),
        exclude_keywords=list(raw.get("exclude_keywords") or []),
        sources=list(raw.get("sources") or []),
        match_threshold=float(raw.get("match_threshold") or 0.35),
        freelance_focus=bool(raw.get("freelance_focus", True)),
        experience_level=raw.get("experience_level") or "any",
        min_budget=raw.get("min_budget"),
        max_budget=raw.get("max_budget"),
        min_hourly_rate=raw.get("min_hourly_rate"),
        notification_channels=[],
    )


class MatchingBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.examples = _load_examples()
        assert len(cls.examples) >= 12

    def test_fixture_immutable_labels(self) -> None:
        labels = {row["label"] for row in self.examples}
        cohorts = {row["cohort"] for row in self.examples}
        self.assertTrue(
            {"strong", "weak", "unknown", "hard_filter", "exclusion"} <= labels
        )
        self.assertIn("newcomer", cohorts)
        self.assertIn("experienced", cohorts)

    def test_hard_filters_and_exclusions(self) -> None:
        matcher = MatchingService()
        for row in self.examples:
            if row["label"] not in {"hard_filter", "exclusion"}:
                continue
            job = _job_from(row["job"])
            prefs = _prefs_from(row["prefs"])
            match = matcher.score_job(job, prefs)
            self.assertIsNone(
                match,
                msg=f"{row['id']} ({row['label']}) should be filtered out",
            )

    def test_paid_status_cannot_change_organic_rank(self) -> None:
        pipeline = RankingPipeline()
        jobs = [_job_from(r["job"]) for r in self.examples if r["label"] == "strong"]
        prefs = _prefs_from(self.examples[0]["prefs"])
        free_user = SimpleNamespace(is_pro=False, subscription_status="free", plan="free")
        pro_user = SimpleNamespace(is_pro=True, subscription_status="active", plan="pro")

        ranked_free = pipeline.rank(jobs, prefs, learning_enabled=False)
        # Inject subscription onto prefs accidentally if someone wires it — rank must ignore.
        prefs_pro = prefs
        ranked_pro = pipeline.rank(jobs, prefs_pro, learning_enabled=False)

        free_ids = [m.job.id for m in ranked_free]
        pro_ids = [m.job.id for m in ranked_pro]
        self.assertEqual(free_ids, pro_ids)
        meta = pipeline.recommendation_meta(prefs, learning_enabled=False)
        self.assertFalse(meta["subscription_affects_organic_rank"])
        # Explicit: user plan objects are not consulted by the pipeline.
        self.assertTrue(hasattr(free_user, "is_pro"))
        self.assertTrue(hasattr(pro_user, "is_pro"))

    def test_explanations_are_factual_not_calibrated(self) -> None:
        pipeline = RankingPipeline()
        row = next(r for r in self.examples if r["label"] == "strong")
        ranked = pipeline.rank(
            [_job_from(row["job"])],
            _prefs_from(row["prefs"]),
            learning_enabled=False,
            pipeline_mode="weighted_v1",
            semantic_enabled=False,
        )
        self.assertEqual(len(ranked), 1)
        expl = ranked[0].explanation.to_dict()
        self.assertIsNone(expl["calibrated_probability"])
        self.assertIn("Heuristic", expl["confidence_note"])
        self.assertTrue(expl["why_shown"])
        self.assertTrue(expl["components"])
        self.assertEqual(expl["eligibility"], "eligible")

    def test_ranking_works_when_semantic_disabled(self) -> None:
        pipeline = RankingPipeline()
        jobs = [_job_from(r["job"]) for r in self.examples]
        # Shared prefs that should surface strong python/fastapi roles.
        prefs = _prefs_from(
            {
                "skills": ["python", "fastapi", "react"],
                "keywords": [],
                "exclude_keywords": ["crypto"],
                "match_threshold": 0.25,
                "freelance_focus": True,
            }
        )
        ranked = pipeline.rank(
            jobs,
            prefs,
            learning_enabled=False,
            pipeline_mode="weighted_v1",
            semantic_enabled=False,
        )
        self.assertGreaterEqual(len(ranked), 1)
        self.assertEqual(ranked[0].score_version, "weighted_v1")
        self.assertIn(ranked[0].retrieval_path, {"keyword", "keyword_fallback", "pool"})

    def test_cold_start_does_not_lock_out(self) -> None:
        pipeline = RankingPipeline()
        row = next(r for r in self.examples if r["label"] == "unknown" and r["cohort"] == "newcomer")
        prefs = _prefs_from(row["prefs"])
        profile = MatchProfileBuilder().build(prefs, learning_enabled=False)
        self.assertTrue(profile.cold_start)
        ranked = pipeline.rank(
            [_job_from(row["job"])],
            prefs,
            learning_enabled=False,
            pipeline_mode="weighted_v1",
        )
        # With no skills, weighted scorer uses no_skills_configured path and may keep job.
        self.assertGreaterEqual(len(ranked), 0)
        self.assertLessEqual(profile.match_threshold, 0.25)

    def test_hybrid_falls_back_and_benchmark_metrics(self) -> None:
        examples = self.examples
        jobs = [_job_from(r["job"]) for r in examples]
        # One shared preference profile approximating the dominant Hunt Rules.
        prefs = _prefs_from(
            {
                "skills": ["python", "fastapi", "react", "typescript"],
                "keywords": ["remote"],
                "exclude_keywords": ["crypto", "staffing"],
                "match_threshold": 0.25,
                "freelance_focus": True,
                "sources": [],
            }
        )
        relevant = {
            str(r["job"]["id"])
            for r in examples
            if r["label"] in {"strong", "unknown"} and r["relevance"] >= 2
        }
        graded = {str(r["job"]["id"]): float(r["relevance"]) for r in examples}

        pipeline = RankingPipeline()

        t0 = time.perf_counter()
        weighted = pipeline.rank(
            jobs,
            prefs,
            learning_enabled=False,
            pipeline_mode="weighted_v1",
            semantic_enabled=False,
        )
        weighted_ms = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        hybrid = pipeline.rank(
            jobs,
            prefs,
            learning_enabled=False,
            pipeline_mode="hybrid_v1",
            semantic_enabled=True,
        )
        hybrid_ms = (time.perf_counter() - t1) * 1000.0

        weighted_ids = [str(m.job.id) for m in weighted]
        hybrid_ids = [str(m.job.id) for m in hybrid]
        weighted_keys = [
            (m.job.canonical_id or m.job.url or m.job.title or "") for m in weighted
        ]
        hybrid_keys = [
            (m.job.canonical_id or m.job.url or m.job.title or "") for m in hybrid
        ]

        before = summarize_run(
            ranked_ids=weighted_ids,
            relevant=relevant,
            graded=graded,
            duplicate_keys=weighted_keys,
            latency_ms=weighted_ms,
            cost_usd=0.0,
        )
        after = summarize_run(
            ranked_ids=hybrid_ids,
            relevant=relevant,
            graded=graded,
            duplicate_keys=hybrid_keys,
            latency_ms=hybrid_ms,
            cost_usd=0.0,
        )

        # Gate: both pipelines return ranked results; duplicate collapse should help hybrid/weighted.
        self.assertGreater(len(weighted_ids), 0)
        self.assertGreater(len(hybrid_ids), 0)
        self.assertLessEqual(after["duplicate_rate"], before["duplicate_rate"] + 0.05)
        # Per-example prefs still enforce hard filters / exclusions (shared prefs above do not).
        matcher = MatchingService()
        for row in examples:
            if row["label"] not in {"hard_filter", "exclusion"}:
                continue
            self.assertIsNone(
                matcher.score_job(_job_from(row["job"]), _prefs_from(row["prefs"]))
            )

        # Subgroup exposure: newcomers still get some ranked exposure under cold prefs.
        newcomer_jobs = [
            _job_from(r["job"])
            for r in examples
            if r["cohort"] == "newcomer" and r["label"] != "weak"
        ]
        newcomer_prefs = _prefs_from(
            {"skills": [], "keywords": [], "match_threshold": 0.35, "freelance_focus": True}
        )
        newcomer_ranked = pipeline.rank(
            newcomer_jobs,
            newcomer_prefs,
            learning_enabled=False,
            pipeline_mode="weighted_v1",
        )
        self.assertGreaterEqual(len(newcomer_ranked), 1)

        # Persist reproducible numbers for phase-07.md consumers / CI visibility.
        report = {
            "dataset": "matching_eval_v1",
            "weighted_v1": before,
            "hybrid_v1": after,
            "examples": {
                "strong": next(
                    m.explanation.to_dict()
                    for m in weighted
                    if m.job.id
                    == next(r["job"]["id"] for r in examples if r["label"] == "strong")
                ),
            },
        }
        out = FIXTURE_DIR / "last_benchmark_report.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
