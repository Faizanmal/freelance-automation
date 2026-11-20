# Release gates

Do **not** treat CI green alone as production readiness.

## Required before promote

1. `pytest` (fastapi + workers) green on target commit  
2. Frontend `lint` + `test` + `build` green  
3. Alembic single head check  
4. `/health/live` 200 and `/health/ready` not `unavailable` on target env  
5. Uptime workflow secret `UPTIME_URL` set; checker fail-closed verified  
6. Migrations applied on disposable clone first; rollback notes reviewed  
7. No secrets in images/logs; Stripe/OAuth only with sandbox keys unless approved  
8. Feature flags / incomplete surfaces not advertised as live verified data  

## Explicit non-goals without approval

- Production deploy  
- Live customer email  
- Real card charges  
- Enabling uncertain commercial scrapers  

## Evidence to attach

- Exact commands + exit codes  
- Request IDs for failed journeys  
- Health JSON (sanitized)  
- Migration revision IDs  
