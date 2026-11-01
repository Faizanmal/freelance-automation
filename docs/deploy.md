# Deploy (locked): single VM backend + Vercel frontend

**Locked topology**

| Piece | Host |
|-------|------|
| Frontend | **Vercel** only |
| API + Celery worker + beat | **One GCP VM** |
| Postgres + Redis | **Same VM** (Docker Compose) |
| TLS / reverse proxy | **Caddy** on the VM (`Caddyfile.api`) |

```
User → Vercel (Next.js)
         │  NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1
         ▼
   GCP VM (e2-medium)
     Caddy → api
     worker + beat
     Postgres + Redis
```

No Cloud Run, Supabase, or Upstash in this locked path.  
(Older hybrid notes: `cloudbuild.yaml`, `compose.workers.yml` — optional alternatives only.)

**Sustaining size:** `e2-medium` (2 vCPU / 4 GB) + **50 GB** SSD. Upgrade to `e2-standard-2` (8 GB) if memory pressure.

**Infra ballpark:** ~$30–50/mo (+ SerpAPI).

---

## 1. Create the VM (GCP Console)

1. **Compute Engine → Create instance**
2. Machine: **e2-medium** (2 vCPU / 4 GB)
3. Boot disk: **Ubuntu 22.04**, **50 GB SSD**
4. Firewall: allow **HTTP** and **HTTPS** (and SSH)
5. Reserve a static external IP; point DNS `api.yourdomain.com` → that IP
6. SSH in

---

## 2. Install Docker on the VM

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# log out / back in
```

Clone the repo (or upload a release):

```bash
git clone YOUR_REPO_URL signaldesk
cd signaldesk
```

---

## 3. Configure `.env`

```bash
cp .env.production.example .env
nano .env
```

Required for this topology:

| Variable | Example |
|----------|---------|
| `POSTGRES_PASSWORD` | long random |
| `JWT_SECRET_KEY` | ≥32 random chars |
| `PUBLIC_DOMAIN` | `api.yourdomain.com` |
| `PUBLIC_API_URL` | `https://api.yourdomain.com/api/v1` |
| `PUBLIC_APP_URL` | `https://your-app.vercel.app` |
| `CORS_ORIGINS` | `https://your-app.vercel.app` |
| `TAVILY_API_KEY` | preferred primary for freelance/jobs/companies |
| `SERPAPI_API_KEY` | fallback (+ Google Jobs / Maps) |
| `EMAIL_SMTP_*` / `EMAIL_FROM` | for verify / digest |

Compose sets `DATABASE_URL` and `REDIS_URL` to the local `db` / `redis` services — you do **not** need Supabase/Upstash URLs.

---

## 4. Start backend stack (no frontend container)

Default compose uses **API-only Caddy** and does **not** start the Next.js container:

```bash
docker compose up -d --build
```

Services: `caddy`, `db`, `redis`, `api`, `worker`, `beat`, `db-backup`, `adminer` (localhost only).

Check:

```bash
curl -sS https://api.yourdomain.com/api/v1/health/ready
docker compose ps
docker compose logs -f worker beat
```

Optional: same-host UI (not the locked path):

```bash
CADDYFILE=./Caddyfile docker compose --profile frontend up -d --build
```

---

## 5. Vercel (frontend only)

1. Import repo → **Root Directory:** `frontend`
2. Env: `NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1`
3. Deploy → ensure VM `CORS_ORIGINS` / `PUBLIC_APP_URL` match the Vercel origin
4. Restart API if you changed CORS:  
   `docker compose up -d api`

---

## Env matrix

| Where | Vars |
|-------|------|
| VM `.env` | `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`, `PUBLIC_DOMAIN`, `CORS_ORIGINS`, `PUBLIC_APP_URL`, `PUBLIC_API_URL`, SerpAPI, SMTP, Stripe |
| Vercel | `NEXT_PUBLIC_API_URL=https://<api-domain>/api/v1` |

Stripe webhook: `https://api.yourdomain.com/api/v1/billing/webhook`

---

## Backups

- `db-backup` service writes dumps under the compose volume; set `S3_BACKUP_BUCKET` (+ AWS keys) for off-box copies.
- Also enable **GCP disk snapshots** on a schedule.

---

## Verify

1. `GET /api/v1/health/ready` → database + redis ok  
2. Vercel app loads; register → verify email  
3. Hunt Rules → refresh → Leads  
4. `docker logs` on `worker` / `beat` show Celery running  

GitHub uptime: set `UPTIME_URL` to `https://api.yourdomain.com/api/v1/health/live`.

---

## Market entry checklist

Use this when opening **public Free + Pro** after a pause or first paid launch.

### 1. Unpause backend

```bash
cd signaldesk   # repo root on the VM
docker compose up -d --build
docker compose ps
curl -sS https://api.yourdomain.com/api/v1/health/live
curl -sS https://api.yourdomain.com/api/v1/health/ready
```

Confirm `api`, `worker`, `beat`, `db`, `redis`, and `caddy` are healthy.

### 2. Secrets required for a usable product

| Area | Vars |
|------|------|
| Auth / CORS | `JWT_SECRET_KEY`, `PUBLIC_*`, `CORS_ORIGINS` |
| Hunters | `TAVILY_API_KEY` and/or `SERPAPI_API_KEY` |
| Mail | `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT`, `EMAIL_USERNAME`, `EMAIL_PASSWORD`, `EMAIL_FROM` |
| Paid Pro | `STRIPE_SECRET_KEY`, `STRIPE_PRICE_PRO`, `STRIPE_WEBHOOK_SECRET`, success/cancel URLs |

Without SMTP, verify + digests fail closed in production. Without hunter keys, Leads stay empty.

### 3. Stripe live

1. Create Pro price in Stripe Dashboard → copy price id into `STRIPE_PRICE_PRO`
2. Webhook endpoint: `https://api.yourdomain.com/api/v1/billing/webhook`  
   Events: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`
3. Paste signing secret into `STRIPE_WEBHOOK_SECRET`
4. `docker compose up -d api` after env change
5. On Vercel `/pricing`: signed-in user → **Upgrade** → Checkout completes → `/billing/me` shows Pro
6. Confirm `dev-activate-pro` is unavailable in production (`404` / no button when Stripe is on)

### 4. Product smoke (after backend is up)

1. Register → verify email (real SMTP)
2. Hunt Rules → save keywords / digest schedule (Free digest max **5**)
3. Desk → **Refresh inventory** (counts against **3** Free manual hunts/day)
4. Leads show ranked fits; open original URL
5. Optional: wait for digest window or trigger digest worker path
6. Hit Free daily hunt cap → API returns upgrade message → Pricing checkout works

### 5. Public trust

- Terms / Privacy pages live; support email reachable (`support@signaldesk.com` or your domain)
- Nav/footer show Desk · Leads · Hunt Rules · Pricing · Help (not legacy Jobs/Alerts/Roadmap)

### 6. Uptime

Set GitHub secret `UPTIME_URL` → `https://api.yourdomain.com/api/v1/health/live` so the uptime workflow can alert if the VM sleeps again.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| CORS | `CORS_ORIGINS` exact Vercel origin (no trailing slash) |
| TLS fail | DNS A record to VM; ports 80/443 open; `PUBLIC_DOMAIN` matches |
| Frontend API 404 | `NEXT_PUBLIC_API_URL` ends with `/api/v1` |
| OOM / killed containers | Resize VM to e2-standard-2 (8 GB) |
| Celery idle | `worker` + `beat` healthy; Redis up |
