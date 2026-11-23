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

## Marketplace operations and pilot gate (Phase 17)

- Moderator, support, source operator roles and superuser boundaries exercised with synthetic accounts; sensitive reads and privileged changes audited.
- Support/dispute escalation, moderation appeals, account restrictions, verification expiry, and reversible source shutdown rehearsed against documented owners and coverage.
- Outcome metrics reconciled against controlled server-side events with denominators, observation windows, and sample sizes; unavailable measures remain unavailable.
- Interview and demand targets in `phase-17-marketplace-operations-growth.md` are planning thresholds only. Never present them as actual counts.
- Payment eligibility, entity/jurisdiction, professional legal/tax/privacy review, customer demand interviews, and staffed support coverage remain explicit external blockers until evidence is recorded.

## Evidence to attach

- Exact commands + exit codes  
- Request IDs for failed journeys  
- Health JSON (sanitized)  
- Migration revision IDs  
