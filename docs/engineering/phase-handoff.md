# Phase handoff

**Current phase completed:** 06 (opportunity trust intelligence) after 01–05  
**Do not deploy** without explicit approval. Ensure `listing_reports` / `listing_report_corrections` tables are created (`create_all` + existing schema_patch for jobs).

## Phase 06 summary

- Structured project extraction (LLM schema-validated + deterministic fallback)
- Evidence registry (verified/observed/reported/unknown) — no universal reputation score
- Transparent risk indicators (not scam verdicts); unknown employer abstains
- Employer research panel + SSRF-safe allowlisted fetch
- Due-diligence checklist on findings; Flag concern → human mod queue
- Eval corpus 43 examples; holdout precision/recall gates in tests

Docs: `phase-06.md`

## Verification evidence

- `tests.test_trust_intelligence`: **15 passed**
- Prior: `tests.test_source_governance` + commercial sources: **25 passed**

## Carry-forward

- Orphan Celery beat / stale sweep wiring
- Playwright + axe CI
- Persistent Redis quarantine DB table (optional)
- Ranking/matching phase on shared inventory (user-specific)

## Next prompt recommendations

1. Matching / ranking quality on shared inventory (keep separate from ingestion + trust channels)
2. Playwright + axe viewport gate
3. Wire orphan Celery beat schedules
