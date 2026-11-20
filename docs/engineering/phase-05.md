# Phase 05 — Reliable opportunity discovery and source governance

## Goal

Build the most trustworthy shared inventory possible — not the largest scrape DB. Discovery ingestion stays separate from user ranking and digest scheduling.

## What shipped

### Source contracts
- Typed registry: `fastapi/app/ingestion/governance.py` (`SourcePolicy` with permission, attribution, allowed fields, rate/budget, TTL, checkpoint, health, operator disable).
- Policy gate: `fastapi/app/ingestion/policy_gate.py` — default-disables restricted (`remotive`, `weworkremotely`, `peopleperhour`, `guru`) and experimental browser sources; blocks missing credentials for conditional search/marketplace adapters.
- Canonical schema: `fastapi/app/ingestion/contracts.py` (`ExternalOpportunity`) + normalizer `normalize.py` (nulls over fabrications; safe HTTP URLs only).
- Adapter surface unchanged (`SOURCE_REGISTRY` fetchers); single gate + normalize path before `JobIngestionService`.

### Reliability
- Per-source leases, circuit breakers, quarantine/dead letters, spend caps: `fastapi/app/ingestion/reliability.py`.
- Wired into `ScrapeService.run`: gate → circuit/budget/lease → fetch → classify → idempotent upsert; empty fetch = `no_results` (not error); one source outage cannot stop others.

### Inventory fields (additive)
- `jobs.work_type`, `compensation_period`, `compensation_currency`, `first_seen_at`, `last_seen_at`, `last_checked_at`, `inventory_state` via model + `schema_patch`.
- Replay touches `last_checked_at`; never auto-republishes expired/removed rows; unique `(source_name, source_id)` prevents duplicate rows on replay.

### Dedup / classification
- Existing external-ID + URL + same-source fuzzy merge retained (conservative; no aggressive cross-board merges).
- Fingerprints via `fingerprint_opportunity`; work-type classifier with evidence stored in enrichment JSON.

### Ops console
- Admin APIs: `/admin/sources`, `/admin/sources/health`, `/admin/sources/quarantine`, `/admin/sources/{key}/disable`, `/admin/inventory/quality`, `/admin/hunt-runs/status`.
- Admin UI section: source table, one-click disable, quality meters, quarantine preview.
- User-facing: attribution via `SOURCE_ATTRIBUTION` + `public_job_payload`; non-http(s) apply URLs stripped; frontend `sanitizeExternalUrl` unchanged.

### API
- Jobs list gains `cursor` (after id) + `next_cursor`; items expose `work_type`, freshness timestamps, `inventory_state`.

## Fixtures & metrics

| Item | Result |
|------|--------|
| Labeled sample | **200** synthetic authorized records (`fastapi/tests/fixtures/permitted_opportunity_sample.jsonl`) |
| Nature | Synthetic — live commercial dumps not redistributed |
| Work-type precision (title/desc/tags, no source prior) | ≥ 0.90 on labeled corpus (asserted in tests) |
| Dedup | Fingerprints unique across 50-sample slice; replay stable |
| Stale link rate | Measured as `stale_marked_rate` on inventory quality sample (ops + tests) |

## Live sources — authorized vs off

**Authorized / prefer when keyed:** RemoteOK, Arbeitnow, Himalayas, Jobicy public APIs; Greenhouse/Lever/Ashby/direct ATS feeds; Tavily→SerpAPI discovery hunters; Reddit/HN/GitHub community when configured.

**Default-off (restricted / experimental):** Remotive, We Work Remotely, PeoplePerHour, Guru, LinkedIn/Upwork browser. No paywall, CAPTCHA, auth, or rate-limit bypass.

## Cost & retention

See `docs/engineering/source-cost-retention.md`.

## Gate checklist

| Gate | Status |
|------|--------|
| No fabricated opportunities in production path | Pass — nulls; fixtures labeled synthetic |
| Replay creates no duplicate rows | Pass — unique constraint + skip path |
| Single provider outage cannot take down feed | Pass — per-source try/circuit/quarantine |
| Source usage capped | Pass — leases + daily budget check |
| Invalid/removed clearly marked | Pass — `is_expired` / `inventory_state`; no auto-republish |
| Users see source + freshness | Pass — attribution + `last_checked_at` / created |

## Tests

```bash
python -m unittest fastapi.tests.test_source_governance fastapi.tests.test_commercial_sources
```

## Out of scope / follow-ups

- Persistent quarantine table (Redis/list today; DB optional).
- Semantic clustering UI for audited split/merge.
- Wire orphan `celery_beat` HN/stale sweep if still disconnected (carry-forward from reliability phase).
