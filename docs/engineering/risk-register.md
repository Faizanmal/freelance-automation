# Risk register

| ID | Pri | Finding | Evidence | Status |
|----|-----|---------|----------|--------|
| R1 | P0 | Uptime checker exited 0 when `UPTIME_URL` unset | `scripts/uptime_check.py` previously returned 0 | **Fixed** Phase 02 — fail closed + CI/workflow guards |
| R2 | P0 | Compose.dev API port default 8002 vs frontend `:8000` | `compose.dev.yml` vs `NEXT_PUBLIC_API_URL` | **Fixed** default host port 8000 |
| R3 | P1 | Readiness returned 200 even when DB would fail mid-check without clear 503 contract | `health.py` | **Improved** — timeouts + 503 `unavailable` |
| R4 | P1 | No scheduler overlap lock → duplicate scrapes/digests under multi-beat | Celery beat schedule + tasks | **Mitigated** — Redis overlap locks |
| R5 | P1 | Public marketing/desk may show prolonged loading without JS | Prior review hypothesis | **Open** — needs browser capture; ErrorBoundary + API timeouts reduce stuck shells |
| R6 | P1 | Lead page size / payload weight | Prior review hypothesis | **Open** — measure after local boot |
| R7 | P1 | Docs vs default sources drift (`hn_hiring` in ARCHITECTURE vs settings default) | `ARCHITECTURE.md` vs `SCRAPE_SOURCES` | **Open** — reconcile in phase 03 |
| R8 | P2 | Dependabot backlog | GitHub alerts (external) | **Open** — review individually, no mass merge |
| R9 | P2 | Dual in-API scrape scheduler + Celery beat can double-hunt | `main.py` lifespan + beat | Documented; keep `SCRAPE_INTERVAL_MINUTES=0` in compose.dev |
| R10 | P2 | No browser smoke in CI | CI workflow | Deferred minimal smoke; unit coverage added |
| R11 | P1 | Optional integrations fail silently | Various hunters | Settings leave keys empty; integrations status endpoint reports readiness |
| R12 | P0 | Secrets in logs / root responses | Root lists sources only | Continue redaction; error handlers must not dump env |
| R13 | P0 | Instant match notify called missing `calculate_match` | [Discovery audit](67d57942-05f3-4243-b235-9de5ca1172ce); `scrape_service.py` | **Fixed** — uses `MatchingService.score_job` |
| R14 | P0 | Digest stamped `last_digest_at` but model/`is_digest_due` use `digest_last_sent_at` | Discovery audit; `digest_service.py` | **Fixed** — writes `digest_last_sent_at` |
| R15 | P1 | Frontend logout cleared localStorage only; JWT not blocklisted | [Auth audit](68583fb3-2a37-4005-ae69-e72cc58e8de0) | **Fixed** — Account Settings + preferences call revoke |
| R21 | P0 | OAuth merged unverified local emails | Auth audit / Phase 03 | **Fixed** — verified-only link |
| R22 | P0 | Register 409 enumerated emails | Auth audit / Phase 03 | **Fixed** — `RegisterResponse` |
| R23 | P1 | No refresh / rotation | Auth audit / Phase 03 | **Mitigated** — refresh cookie+body; access still Bearer |
| R16 | P2 | Privacy page claimed auth cookies; auth is Bearer + localStorage | Auth audit; `privacy/page.tsx` | **Fixed** — copy corrected |
| R17 | P1 | `workers/scheduler/celery_beat.py` (HN + stale sweep) unwired vs `workers/app.py` | Discovery + [inventory](6fde7a34-65d1-44e8-afb4-26f8d6c13c62) | **Open** — merge carefully; avoid double schedules |
| R18 | P2 | `job_applications` via `create_all` only; no Alembic revision | Inventory audit | **Open** — additive migration later |
| R19 | P2 | Dual hunt: API `SCRAPE_INTERVAL_MINUTES` + Celery beat | Inventory audit | Keep compose.dev interval 0; prod review |
| R20 | P2 | ARCHITECTURE / `database/schema.sql` aspirational vs live models | Inventory audit | Docs drift — reconcile in phase 03 |

## Hypotheses (need repro before defect label)

- Non-JS reader sees perpetual loading on public site
- Lead list performance regression on large inventories
