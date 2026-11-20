# Runbook — worker backlog

## Symptoms

- `/health/ready` shows `workers: idle` or `worker_heartbeat: stale`  
- Digests/scrapes delayed; Redis queue depth growing  

## Check

```bash
docker compose -f compose.yml ps worker beat redis
# Inside worker container or host with REDIS_URL:
celery -A workers.app.celery_app inspect active
celery -A workers.app.celery_app inspect reserved
```

## Mitigate

1. Restart `worker` then `beat` (beat alone cannot consume).  
2. Confirm `REDIS_URL` reachable; fix auth/TLS.  
3. If poison messages: inspect Redis list `celery_dlq` (JSON entries with `run_id`).  
4. Replay carefully: re-queue only idempotent tasks (`scrape_jobs`, digests) after fixing root cause — do not blindly replay notifications without dedupe review.  
5. Scale concurrency only after confirming DB pool and provider rate limits.

## Done when

- Heartbeats `ok`, queue drains, ready not stuck `unavailable`.
