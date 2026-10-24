# Signal Desk — Freelance Discovery Desk

Find real freelance and contract opportunities outside crowded marketplace bid wars. Set **Hunt Rules**, background **hunters** fill a shared pool, ranked **Leads** and an email **digest** send you to the original listing. No fake jobs. No auto-apply.

## Product (V1)

| Surface | Role |
|---------|------|
| **Hunt Rules** (`/preferences`) | Keywords, exclude, budget, location, freelance focus, digest schedule |
| **Leads** (`/leads`) | Ranked fits with why/risks; primary CTA = **Open original**; Save / Skip |
| **Desk** (`/`) | Overview + refresh inventory |
| **Digest** | Email on your show clock (days/time/timezone), not tied 1:1 to scrape time |

**Two clocks**

- **Hunt clock** — system schedule (`SCRAPE_INTERVAL_MINUTES` / Celery beat) fills the job pool
- **Show clock** — your digest days/time/timezone + live Leads

## What works now

- **API** (`fastapi/`) — FastAPI + Postgres by default (SQLite via `DATABASE_URL` still supported)
- **V1 hunter spine (default)** — `serpapi_freelance`, `serpapi_jobs`, `serpapi_companies` when `SERPAPI_API_KEY` is set
- **Post-V1 volume (opt-in)** — `reddit_hiring` (official Reddit API, `[Hiring]` only)
- **Optional free boards** — RemoteOK, Arbeitnow, Himalayas, Jobicy (not the product identity)
- **Matching + freelance focus** — contract/freelance boost; downrank full-time / W2 noise
- **Lead findings** — score, signals, risks; Save/Skip persisted per user
- **Email digest** — Celery `process_lead_digests` every 15 minutes checks show-clock windows
- **Auth** — register, verify, password reset, optional 2FA
- **UI** — Desk / Leads / Hunt Rules / Account (Sources page exists but is off main nav)

Marketplaces (Upwork, Freelancer, etc.) remain in code for experiments but are **off the default schedule** and not the V1 story. Browser Playwright sources stay experimental.

## Quick start

```bash
git clone <your-repo-url> freelance_automation
cd freelance_automation
```

### Docker (full stack)

```bash
cd fastapi
copy .env.example .env
# Set at least: SERPAPI_API_KEY, JWT secret, DATABASE_URL (compose provides DB)
cd ..
docker compose up --build
```

- Frontend: http://localhost:3000  
- API docs: http://localhost:8000/docs  

### Local development

**API**

```bash
cd fastapi
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # macOS / Linux
pip install -r requirements.txt
copy .env.example .env
docker compose up -d db redis   # from repo root or fastapi/ as documented
uvicorn app.main:app --reload --port 8000
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 → sign up → verify email → **Hunt Rules** → refresh inventory → **Leads**.

### Seed / hunt inventory

Default sources come from `SCRAPE_SOURCES` (V1 spine). Authenticated scrape:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs/scrape ^
  -H "Content-Type: application/json" ^
  -H "Authorization: Bearer YOUR_JWT" ^
  -d "{\"limit\":20,\"notify_matches\":false,\"background\":false}"
```

Or:

```bash
python workers/run_scrape.py --api http://127.0.0.1:8000 --token YOUR_JWT
```

Live smoke (register → Hunt Rules → findings):

```bash
set API_URL=http://127.0.0.1:8000/api/v1
python scripts/live_test.py
```

## Connect hunters

### SerpAPI (V1 spine — required for default hunt)

1. Create a key at [SerpAPI](https://serpapi.com/)
2. Set in `fastapi/.env`:
   ```env
   SERPAPI_API_KEY=...
   SCRAPE_SOURCES=serpapi_freelance,serpapi_jobs,serpapi_companies
   ```
3. Optional: tune `SERPAPI_FREELANCE_QUERY`, `SERPAPI_JOBS_QUERY`, `SERPAPI_COMPANIES_QUERY`
4. Company/ATS path uses batched `site:` queries (Greenhouse/Lever/Ashby-style hosts included for discovery; high-traffic aggregators like LinkedIn/Indeed are filtered out)

Scrape one mode:

```json
{"sources":["serpapi_freelance"],"limit":15}
```

### Reddit hiring (W5 volume — opt-in)

1. Open [Reddit apps](https://www.reddit.com/prefs/apps) → **create another app**
2. Choose **script** (personal/server use; needs a secret)
3. **redirect uri:** `http://127.0.0.1:8000/` (required by the form)
4. Copy **client id** (under the app name) and **secret**
5. Set in `fastapi/.env`:
   ```env
   REDDIT_CLIENT_ID=...
   REDDIT_CLIENT_SECRET=...
   REDDIT_USER_AGENT=signaldesk:discovery:v1 (by /u/YOUR_REDDIT_USERNAME)
   REDDIT_SUBREDDITS=forhire,hiring
   SCRAPE_SOURCES=serpapi_freelance,serpapi_jobs,serpapi_companies,reddit_hiring
   ```
6. Restart/reload the API, then scrape. Only posts with `[Hiring]` are ingested; `[For Hire]` is skipped.

Do **not** use “installed app” (no secret). “Web app” is unnecessary for this read-only hunter.

### Marketplace connectors (optional / off by default)

Upwork and Freelancer adapters still exist for licensed/experimental use. They are **not** in `V1_DEFAULT_HUNTERS`. See `GET /integrations/status` and older Upwork/Freelancer env vars in `.env.example` if you enable them deliberately.

## Main endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/jobs` | List stored jobs |
| POST | `/jobs/scrape` | Run hunters / ingest (auth; verified email) |
| GET | `/integrations/status` | Credential / source availability |
| GET/PUT | `/preferences/me` | Hunt Rules CRUD (digest schedule, freelance_focus, …) |
| GET | `/preferences/findings` | Auth’d leads (`freelance_focus`, Save/Skip filtering) |
| PUT | `/preferences/leads/{job_id}/action` | `save` / `skip` / `clear` |
| GET | `/preferences/demo-findings` | Demo leads (no auth) |
| POST | `/auth/register` | Create user |
| POST | `/auth/login` | JWT login |
| POST | `/notifications/send` | Send alert (auth) |

## Commercial plans (direction)

| Plan | Includes |
|------|----------|
| Free | Hunt Rules, V1 SerpAPI spine when keyed, ranked Leads, email digest, Save/Skip |
| Pro | Higher hunt density / digest caps, optional Maps + multi-channel alerts; not marketplace bid bots |

Configure Stripe with `STRIPE_SECRET_KEY`, `STRIPE_PRICE_PRO`, and `STRIPE_WEBHOOK_SECRET` when charging. Local/dev: **Activate Pro (dev)** on `/pricing` if Stripe is unset.

## Production launch

**Locked:** **Vercel** (frontend) + **one GCP VM** (API + worker + beat + Postgres + Redis + Caddy) — see **[docs/deploy.md](docs/deploy.md)**.

```bash
# on the VM (e2-medium recommended)
copy .env.production.example .env
# POSTGRES_PASSWORD, JWT, PUBLIC_DOMAIN, CORS_ORIGINS (Vercel URL), SERPAPI, SMTP
docker compose -f compose.production.yml up -d --build
```

Vercel: Root Directory `frontend`, `NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1`.

Set GitHub secret `UPTIME_URL` for the uptime workflow. Verify `/api/v1/health/live` and `/ready`.

Listings are returned as **excerpts + attribution + original URL** — not full republished boards.

## Layout

```
freelance_automation/
  backend/          # application services (matching, digests, scrape, …)
  fastapi/          # product API + hunters under app/integrations
  frontend/         # Next.js Signal Desk UI (deploy on Vercel)
  scrapers/         # Playwright / HTTP adapters (experimental browsers)
  workers/          # Celery tasks + scrape CLI + digest beat
  database/         # models + Alembic migrations
  scripts/          # live_test.py, uptime_check.py
  docs/deploy.md    # locked: single VM backend + Vercel
  compose.production.yml
  Caddyfile.api     # API-only edge (default)
  ARCHITECTURE.md   # module vision
```

## Notes

- Default DB is **Postgres**. Schema patches / migrations add Hunt Rules + `user_lead_actions` columns/tables.
- Default `SCRAPE_NOTIFY_MATCHES=false` — digests own the show clock; scrape-time pings are skipped when `digest_mode` is on.
- Soft-launch gate unit tests: `fastapi/tests/test_v1_soft_launch_gates.py`
- Without `EMAIL_SMTP_*`, auth/digest mail is logged only in dev.
- Keep secrets local: never commit `fastapi/.env` or `frontend/.env.local`.
