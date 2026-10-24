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
| `SERPAPI_API_KEY` | your key |
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

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| CORS | `CORS_ORIGINS` exact Vercel origin (no trailing slash) |
| TLS fail | DNS A record to VM; ports 80/443 open; `PUBLIC_DOMAIN` matches |
| Frontend API 404 | `NEXT_PUBLIC_API_URL` ends with `/api/v1` |
| OOM / killed containers | Resize VM to e2-standard-2 (8 GB) |
| Celery idle | `worker` + `beat` healthy; Redis up |
