# Phase 07 — Explainable hybrid matching and adaptive recommendations

## Intent

Upgrade the deterministic weighted ranker without losing explainability. Optimize for **qualified opportunities and successful actions**, not raw listing volume. Keep fit independent from trust/risk. Never use subscription/plan in organic native rank.

## What shipped

| Area | Location |
|------|----------|
| Typed match profile | `backend/application/services/ranking/profile.py` |
| Versioned score explanations | `ranking/explanation.py` |
| **SQL ILIKE candidate stage** | `SQLAlchemyJobRepository.list_match_candidates` → findings/matches/digest |
| Keyword + optional semantic retrieval | `ranking/retrieval.py`, `ranking/embeddings.py` |
| Ranking pipeline + fallback | `ranking/pipeline.py` |
| Diversity / duplicate collapse | `ranking/diversity.py` |
| Eligibility rejects explained | `MatchingService.explain_ineligibility` + `ineligible_samples` on API |
| Offline metrics | `ranking/benchmark.py` |
| Consent-gated learning | `match_feedback.py` + purpose `ranking_personalization` |
| Structured feedback API + Leads UI | `POST /match-feedback`; Save/Skip reasons, hide source, apply-click, outcomes |
| Profile / meta / reset APIs | `/match-profile`, `/recommendation-meta`, `/learned-affinities/reset` |
| Recommendation TTL cache | keyed by user/prefs/version; invalidated on Hunt Rules + actions |
| Embedding persist + reindex | `EmbeddingIndex.persist_dirty`; `POST /embeddings/reindex`; Celery `tasks.reindex_embeddings` |
| Findings attach | `lead_findings.py` (`fit_score`, `explanation`, `why_shown`) |
| Desk UI | Hunt Rules match profile + consent/reset; Leads why-shown / missing quals / feedback |
| Privacy | Privacy Center consent for ranking personalization |

### Locked decisions
- Default / rollback: `MATCH_PIPELINE=weighted_v1` (existing `MatchingService`).
- Semantic retrieval off by default: `MATCH_SEMANTIC_RETRIEVAL=0`.
- **No pgvector this phase** — JSON `embedding_vector` + in-process cosine; revisit when ANN latency dominates.
- Hybrid failure → weighted_v1 keyword fallback.
- Learning requires explicit `ranking_personalization` consent; apply-click is not success (no Save row invented).
- Cold start: editable Hunt Rules + wider threshold when no skills; newcomers are not locked out.
- Sensitive traits are never inferred (`sensitive_traits_inferred: false`).
- Candidate stage is SQL ILIKE (not Postgres `tsvector` FTS yet); semantic remains optional BoW cosine.

### Still deferred (explicit)
- Postgres `tsvector` / `pgvector` ANN indexes
- Large production holdout before promoting `hybrid_v1`
- Editable hard/soft kinds as first-class preference fields (today: derived from Hunt Rules)

## Evaluation

| Item | Value |
|------|-------|
| Corpus | `fastapi/tests/fixtures/matching_eval/` — **15** labeled examples |
| Labels | strong, weak, unknown, hard_filter, exclusion |
| Subgroups | newcomer vs experienced (action/history cohort); freelance_focus — **non-sensitive only** |
| Report | `last_benchmark_report.json` (written by tests) |

### Before / after (reproducible, matching_eval_v1)

| Metric | weighted_v1 (before / default) | hybrid_v1 (semantic on) |
|--------|--------------------------------|-------------------------|
| Precision@5 | 1.0000 | 1.0000 |
| Precision@10 | 0.7778 | 0.7778 |
| nDCG@10 | 0.9298 | 0.9298 |
| Recall@20 | 0.8750 | 0.8750 |
| Duplicate rate | 0.0000 | 0.0000 |
| Latency (ms) | ~2.1 | ~3.2 |
| Cost (USD) | 0.000 | 0.000 |

**Interpretation:** On this synthetic set, hybrid retrieval does not beat weighted_v1 quality; it adds a small latency cost. Keep **weighted_v1 as default**. Promote hybrid only after a larger holdout improves P@k / nDCG without cost regressions — not by automatic LLM adoption.

### Explanation examples

**Strong** (Python/FastAPI/React contract): fit ≈ 0.90; matched skills; missing `typescript`; confidence band `high`; `calibrated_probability: null`.

**Weak / filtered**: source whitelist miss, exclude-keyword hit, budget hard filter, or non-opportunity noise → not ranked (`score_job` returns `None`).

**Unknown / cold start**: empty skills → starter threshold 0.25; confidence band `unknown`; still eligible for ranking.

## Gate

| Gate | Status |
|------|--------|
| Reproducible before/after benchmark + strong/weak/unknown examples | Pass (this doc + fixtures) |
| Hard filters and user exclusions work | Pass (`test_hard_filters_and_exclusions`) |
| Paid status cannot change organic native rank | Pass (`test_paid_status_cannot_change_organic_rank`) |
| Rank explanations factual; no fake calibrated probability | Pass |
| Ranking works when AI/semantic disabled | Pass (`weighted_v1`) |
| Existing ranker remains default / fallback | Pass (`MATCH_PIPELINE`, hybrid exception path) |

## Tests

```bash
cd fastapi
set PYTHONPATH=..;.
.venv/Scripts/python -m unittest tests.test_ranking_pipeline tests.test_matching_benchmark tests.test_matching -v
```

## Rollout / rollback

1. Ship with `MATCH_PIPELINE=weighted_v1`, `MATCH_SEMANTIC_RETRIEVAL=0`.
2. Opt-in hybrid on staging: `MATCH_PIPELINE=hybrid_v1` + `MATCH_SEMANTIC_RETRIEVAL=1`.
3. Compare offline + live proxy metrics (save/pitch rates, not clickbait volume).
4. Rollback: set `MATCH_PIPELINE=weighted_v1` (instant; no model deploy).

## Non-claims

This phase does **not** claim calibrated hire probability, that hybrid embeddings improve production ranking, or that personalization replaces Hunt Rules. Trust/risk remain Phase 06 channels and are not blended into fit.
