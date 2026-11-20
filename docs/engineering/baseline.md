# Baseline (Phase 01 audit)

**Audit date:** 2026-11-19  
**Branch:** `main`  
**Commit:** `930e243d3b9c4f765c7d65f1216a7a2051d11889`  
**Worktree:** clean (audit start); Phase 02 reliability changes follow on same branch worktree.

## Stack (actual)

| Layer | Reality |
|-------|---------|
| API | FastAPI under `fastapi/app` (`uvicorn app.main:app`) |
| Domain services | `backend/application/services/*` (shared by API + workers) |
| DB | Postgres via SQLAlchemy async + Alembic (`database/`) |
| Cache/broker | Redis (`REDIS_URL`); Celery worker + beat (`workers/`) |
| Frontend | Next.js App Router (`frontend/`), Node 22 in CI |
| AI | Optional LLM providers in `ai/` + settings keys |
| Scrapers | `scrapers/` + FastAPI `app/ingestion` + `app/integrations` |
| Python | CI `3.12`; local host may differ — use Docker or match CI |

## Topology

- **Dev:** `compose.dev.yml` — api, worker, beat, db, redis, frontend, adminer  
  - API host port default **8000** (was mismatched 8002 vs frontend `NEXT_PUBLIC_API_URL`)  
  - Frontend: `http://localhost:3000` → API `http://localhost:8000`
- **Prod-ish:** `compose.yml` / `compose.production.yml` + Caddy + `cloudbuild.yaml`
- Dual route mounts: `/api/v1/*` and bare `/*` for the same routers

## Auth / billing (implemented)

- Register, email verify, password reset, logout blocklist — `fastapi/app/api/v1/auth.py`
- Optional TOTP 2FA — present in auth/users surfaces
- Google / GitHub OAuth — env-gated (`GOOGLE_*`, `GITHUB_*`)
- Stripe checkout + webhook + cancel — `fastapi/app/api/v1/billing.py` (`STRIPE_*`)

## Discovery path (code-backed)

Hunt Rules (`preferences`) → Celery/`ScrapeService` hunters → ingest/dedupe (`job_ingestion`, `duplicate_detection`) → match/`lead_findings` → Leads UI Save/Skip → optional proposal draft → show-clock digest (`digest_service` + `process_lead_digests`).

**Default sources:** `serpapi_freelance,serpapi_jobs,serpapi_companies` (Tavily primary when keyed; SerpAPI fallback).  
**Opt-in:** Reddit, boards, marketplaces, Playwright — registered but not all scheduled.

## Startup recipe (repeatable)

```bash
# From repo root
cd fastapi && copy .env.example .env   # Windows; add TAVILY/SERPAPI as needed
cd ..
docker compose -f compose.dev.yml up --build
# Frontend http://localhost:3000  API docs http://localhost:8000/docs
```

Local API without full compose:

```bash
docker compose -f compose.dev.yml up -d db redis
cd fastapi && python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm ci && npm run dev
```

## Verification commands

| Command | Purpose |
|---------|---------|
| `cd fastapi && python -m pytest tests -q` | API/unit |
| `PYTHONPATH=. python -m pytest workers/tests -q` | Workers |
| `cd frontend && npm ci && npm run lint && npm run test && npm run build` | Frontend |
| `python scripts/uptime_check.py` | Must **fail** if `UPTIME_URL` unset |
| `python scripts/live_test.py` | Needs running API + secrets for full path |

## Gaps / blocked without secrets

- Live Tavily/SerpAPI/Reddit/Stripe/OAuth end-to-end
- Production uptime secret `UPTIME_URL`
- Browser E2E against staging (Playwright suite not yet wired in CI; Phase 02 adds fail-closed checks + unit coverage)

## Metrics to instrument next

- Time to first useful lead (signup → first non-skipped finding)
- Stale/dead listing rate (expiration sweep)
- False-positive skip rate (Save/Skip feedback)
- Source failure ratio per hunter
- Provider spend (Tavily/SerpAPI/LLM)
