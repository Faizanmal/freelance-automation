# Phase 02 — Reliability architecture

## Scope

Production foundation: health, uptime, errors/request IDs, worker locks/DLQ, frontend failure UX, CI hardening, runbooks. No prod deploy.

## Changes

| Area | Change |
|------|--------|
| Uptime | Fail when `UPTIME_URL` missing; reject non-200 / bad JSON / timeout |
| Health | Timeouts; 503 `unavailable`; `degraded` for worker/beat issues; heartbeats |
| API | `RequestIdMiddleware`; envelope `{detail,code,request_id}` |
| Workers | Overlap locks, run IDs, retry jitter, heartbeat touch, DLQ retains run_id |
| Frontend | `ErrorBoundary`; 25s request timeout; 401 clears session |
| Compose | API host port default 8000 |
| CI | Alembic head check; uptime fail-closed step; workflow secret guard |
| Docs | baseline, architecture, risks, decisions, gates, runbooks, handoff |

## Commands / results (2026-11-19, local Windows agent host)

| Command | Result |
|---------|--------|
| `pytest tests/test_uptime_check.py tests/test_health_ready.py ../workers/tests/test_locks.py -q` | **11 passed** |
| `pytest tests -q` (fastapi) | **209 passed, 2 skipped** |
| `python scripts/uptime_check.py` with `UPTIME_URL` unset | **exit 1** (fail closed) |
| Alembic single-head check | **pass** (`20261111_add_custom_webhook_url`) |
| `vitest` ErrorBoundary | **1 passed** |

Latency note (same host): focused reliability suite ~13s; full API suite ~41s. No production baseline available for before/after.

## Rollback

- Revert Phase 02 commit(s).  
- Uptime secret must remain set in GitHub or workflow fails (intentional).  
- No DB migrations in this phase.

## Costs

Negligible compute; Redis keys for locks/heartbeats (TTL ≤ 1h).

## Next (Phase 03 suggestion)

Reconcile source registry docs vs defaults; thin oversized lead UI with regression tests; add minimal Playwright smoke against compose; Dependabot triage one critical at a time.
