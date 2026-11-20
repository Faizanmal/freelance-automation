# Runbook — database outage

## Symptoms

- `/health/ready` → 503 `unavailable`, `database: down:*`  
- API writes fail; workers error on session  

## Check

```bash
docker compose -f compose.dev.yml ps db
# or production compose
curl -sS "$API/health/ready"
```

Do **not** paste connection strings into tickets.

## Mitigate

1. Confirm Postgres process / managed instance status.  
2. Restore from latest backup onto a **disposable** instance first (`scripts/pg_dump.sh` / `docs/deploy.md`).  
3. Point staging `DATABASE_URL` at restored clone; run `alembic upgrade head`.  
4. Only after verification, cut traffic / update prod URL with approval.  

## Rollback / restore drill

1. `pg_dump` from healthy snapshot.  
2. Create empty DB; restore dump.  
3. Run app against restore; hit `/health/ready` and one authenticated read.  
4. Record time-to-recover.
