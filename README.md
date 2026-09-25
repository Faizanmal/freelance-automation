# Freelance Intelligence / Signal Desk

Live job intelligence: scrape public remote-job APIs, store and dedupe listings, score matches against your preferences, and fire multi-channel alerts.

## What works now

- **API** (`fastapi/`) — FastAPI app with Postgres by default (SQLite still supported via `DATABASE_URL`)
- **Live public boards** — RemoteOK, Remotive, Arbeitnow, We Work Remotely, Himalayas, Jobicy
- **Official marketplace APIs** — Upwork (GraphQL + OAuth) and Freelancer.com
- **Optional community connectors** — PeoplePerHour and Guru through Apify actors
- **SerpAPI discovery (Pro)** — Google Search freelance leads, Google Jobs, company careers pages, Maps outreach
- **Enrichment / apply drafts** — multi-provider LLM fallback: Groq → NVIDIA → Gemini → OpenAI → Anthropic (heuristic/template if none configured)
- **Ingestion** — persist jobs, skip duplicates, same-source fuzzy merges
- **Matching** — keyword / budget / enrichment-aware scoring
- **Lead findings** — decision digest with signals, risks, and draft/watch/skip actions
- **Freelance focus** — source-aware boost for marketplace/contract leads; downrank full-time noise
- **Durable alerts** — authenticated notification history + deliveries stored in DB
- **Scheduler** — `SCRAPE_INTERVAL_MINUTES` in-process, or `workers/run_scrape.py --interval-minutes N`
- **UI** (`frontend/`) — Signal Desk with auth, preferences, jobs, matches, alerts

### Connect Upwork

1. Create an app at [Upwork Developer](https://www.upwork.com/developer/)
2. Set redirect URI to `http://127.0.0.1:8000/integrations/upwork/callback`
3. Put `UPWORK_CLIENT_ID` / `UPWORK_CLIENT_SECRET` in `fastapi/.env`
4. Visit http://127.0.0.1:8000/integrations/upwork/authorize and approve
5. Scrape: `POST /jobs/scrape` with `{"sources":["upwork"],"limit":20}`

Or set `UPWORK_ACCESS_TOKEN` (+ optional `UPWORK_REFRESH_TOKEN`) directly.

### Connect Freelancer.com

1. Create an API app / OAuth token in the Freelancer developer portal
2. Set `FREELANCER_OAUTH_TOKEN` in `fastapi/.env`
3. Scrape: `POST /jobs/scrape` with `{"sources":["freelancer"],"limit":20}`

Check connection status: `GET /integrations/status`

### Connect PeoplePerHour and Guru

Neither platform currently exposes a stable, supported public job-search API.
These connectors therefore use clearly labeled Apify community actors:

1. Set `APIFY_TOKEN` in `fastapi/.env`
2. Optionally override `PEOPLEPERHOUR_ACTOR_ID` or `GURU_ACTOR_ID`
3. Scrape with `{"sources":["peopleperhour","guru"],"limit":20}`

Actor usage may be billed by Apify. Fiverr and Contra are intentionally not
presented as job sources: Fiverr exposes seller services rather than client job
postings, and Contra has no public opportunities feed.

### Connect SerpAPI discovery (freelance + jobs)

1. Create a key at [SerpAPI](https://serpapi.com/)
2. Set `SERPAPI_API_KEY` in `fastapi/.env`
3. Optionally tune `SERPAPI_FREELANCE_QUERY` / `SERPAPI_JOBS_QUERY`
4. Activate Pro, then scrape:
   - `{"sources":["serpapi_freelance"],"limit":15}`
   - `{"sources":["serpapi_jobs"],"limit":15}`
   - `{"sources":["serpapi_companies"],"limit":15}`
   - `{"sources":["serpapi_maps"],"limit":15}`

Optional Maps location bias: set `SERPAPI_MAPS_LL` like `@37.77,-122.42,14z`.
Company discovery searches a curated company allowlist (plus low-traffic ATS tenants) via
batched `site:` queries. High-traffic boards (LinkedIn, Dice, Greenhouse, Workable, etc.)
are filtered out. It does not crawl HTML or extract contact info off-platform.

## Quick start

Clone the repo, then copy env templates — never commit real `.env` files (they are gitignored).

```bash
git clone <your-repo-url> freelance_automation
cd freelance_automation
```

### The Easy Way: Docker (Full Stack)

The simplest way to run the entire project (Frontend, API, DB, and Redis) is using Docker Compose from the root directory.

```bash
# 1. Setup API env variables
cd fastapi
copy .env.example .env

# 2. Go back to root and start everything
cd ..
docker compose up --build
```

- **Frontend:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs

### The Manual Way: Local Development

If you prefer to run the components separately for development:

#### 1. API

```bash
cd fastapi
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env

# Start Postgres & Redis (required)
docker compose up -d db redis
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000/docs

#### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 — use **Pull live jobs** on the desk.

### Seeding jobs

Seed jobs via API:

```bash
curl -X POST http://127.0.0.1:8000/jobs/scrape -H "Content-Type: application/json" -H "Authorization: Bearer YOUR_JWT" -d "{\"sources\":[\"remoteok\",\"arbeitnow\",\"himalayas\",\"jobicy\"],\"limit\":40}"
```

Or from the repo root:

```bash
python workers/run_scrape.py --api http://127.0.0.1:8000 --token YOUR_JWT
```

The worker and manual scrape endpoint require an authenticated user token. Sign
in through the UI, then pass the JWT with `--token` or `SIGNAL_DESK_TOKEN`.

## Main endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/jobs` | List stored jobs |
| POST | `/jobs/scrape` | Fetch selected sources and ingest (auth required) |
| GET | `/integrations/status` | Source availability and credential status |
| POST | `/jobs/ingest` | Ingest a single job payload (auth required) |
| POST | `/jobs/detect-duplicate` | Compare against DB jobs (auth required) |
| GET | `/preferences/demo-matches?keywords=python,react` | Rank matches (no auth) |
| GET | `/preferences/demo-findings?keywords=python,react` | Lead findings digest (no auth; `freelance_focus=true` by default) |
| POST | `/auth/register` | Create user + default preferences |
| POST | `/auth/login` | JWT login |
| GET/PUT | `/preferences/me` | Auth’d preference CRUD |
| GET | `/preferences/matches` | Auth’d matches |
| GET | `/preferences/findings` | Auth’d lead findings (`freelance_focus` supported) |
| POST | `/notifications/send` | Send an authenticated user alert |


## Production launch

```bash
copy .env.production.example .env
# Replace all required values and use public HTTPS origins/URLs.
docker compose -f compose.production.yml up -d --build
```

### Commercial plans

| Plan | Includes |
|------|----------|
| Free | RemoteOK + Arbeitnow + Himalayas + Jobicy (attributed excerpts), lead scoring, email alerts, proposal draft starter |
| Pro ($19/mo) | Upwork + Freelancer APIs, SerpAPI discovery (freelance + jobs + companies + Maps), multi-channel alerts, higher scrape limit, proposal drafts |

Remotive, We Work Remotely, PeoplePerHour, and Guru remain registered for demos but are **blocked from commercial scrapes** until written licensing/permission exists.

Configure Stripe with `STRIPE_SECRET_KEY`, `STRIPE_PRICE_PRO`, and `STRIPE_WEBHOOK_SECRET`.
Webhook endpoint: `POST /billing/webhook`. In local/dev without Stripe, use **Activate Pro (dev)** on `/pricing` or Preferences.

Per-user alert destinations live under Preferences (`alert_email`, Slack/Telegram/Discord/WhatsApp).
Listings are returned as **excerpts with source attribution** and original apply links — not full republished boards.

The production stack runs database migrations before API startup, uses
non-root application containers, persists Postgres and Redis data, and fails
fast when the JWT secret or CORS configuration is unsafe. Put ports 3000 and
8000 behind a TLS reverse proxy or managed load balancer. Verify
`/health/live` and `/health/ready` after deployment.

## Layout

```
freelance_automation/
  backend/          # domain-driven service layer and orchestrator
  fastapi/          # product API
  frontend/         # Next.js Signal Desk UI
  scrapers/         # Playwright framework + HTTP source adapters
  workers/          # scrape CLI
  ai/               # LLM analysis providers (optional enrichment)
  database/         # expanded schema design notes
  ARCHITECTURE.md   # long-term module vision
```

## Notes

- Default DB is **Postgres** (`postgresql+asyncpg://postgres:postgres@localhost:5432/freelance`). Run `docker compose up -d db` from `fastapi/`. For local SQLite instead, set `DATABASE_URL=sqlite+aiosqlite:///./freelance.db`.
- LLM apply/enrichment tries providers in order **Groq → NVIDIA → Gemini → OpenAI → Anthropic**; only keys you set are used.
- Upwork/LinkedIn need authenticated browser scrapers; the Playwright framework in `scrapers/core` is ready for those next.
- Unconfigured notification channels return a failed delivery with
  `provider_not_configured`; configure at least one provider before enabling alerts.
- Keep secrets local: `fastapi/.env`, `frontend/.env.local`, `*.db`, `.venv/`, and `node_modules/` stay out of git. Commit only `*.example` env templates.
