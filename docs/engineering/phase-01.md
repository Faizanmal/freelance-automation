# Phase 01 — Repository audit

## Scope

Audit only; no sweeping refactors. Establish baseline artifacts under `docs/engineering/`.

## Inventory highlights

- **Commit:** `930e243` on `main`  
- **CI:** Python 3.12 compileall + pytest; Node 22 lint/test/build; uptime workflow  
- **API routers:** auth, billing, health, integrations, jobs, notifications, preferences, users, admin, roadmap, feedback, telemetry  
- **Workers:** scrape, enrich, notify, drip, digests, stale sweep; DLQ list `celery_dlq`  
- **Frontend journeys:** Desk `/`, Leads, Hunt Rules `/preferences`, Account, Pricing, Status  

## Journey traces (status)

| Journey | Trace status | Evidence |
|---------|--------------|----------|
| Discovery → Leads → Save/Skip → digest | Code-backed | Services + Celery beat; live proof needs API keys |
| Signup / verify / reset / 2FA | Implemented | `auth.py` + tests |
| OAuth Google/GitHub | Implemented, env-gated | Settings + auth routes |
| Stripe checkout/webhook/cancel | Implemented, env-gated | `billing.py` |
| Uptime | **Was defective** | Exited 0 without URL — fixed in Phase 02 |

## Prior findings

| Item | Result |
|------|--------|
| Uptime missing URL | **Reproduced** — exit 0; now exit 1 |
| Non-JS loading | Hypothesis — not browser-captured this session |
| Lead page large | Hypothesis |
| Docs/source drift | Confirmed (`hn_hiring` docs vs defaults) |
| Dependabot | External backlog — do not mass-merge |

## Fixture / journey priorities

1. Register → verify (dev) → set Hunt Rules → findings list  
2. Save/Skip persistence  
3. Digest due window unit tests  
4. Billing plan gates without Stripe  
5. Health live/ready + uptime fail-closed  

## Phase 02 plan (executed next)

Reliability foundation: health truthfulness, uptime fail-closed, request IDs, error envelope, worker locks/heartbeats, frontend error/timeout, CI migration + uptime guards, runbooks.
