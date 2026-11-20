# Decision log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-11-19 | Keep FastAPI + Next + Postgres + Redis + Celery; no new microservice framework | Master directive + existing production path |
| 2026-11-19 | Fail closed on missing `UPTIME_URL` | Prior “quiet local” exit-0 masked broken monitoring |
| 2026-11-19 | Readiness 503 only for critical deps; workers/beat stale → `degraded` 200 | Uptime can stay green during worker blips; deploy probes can treat degraded separately |
| 2026-11-19 | Error envelope adds `code`/`request_id` without removing `detail` | Frontend and clients already parse `detail` |
| 2026-11-19 | Redis overlap locks for scheduled tasks | Prevent duplicate side effects without schema migration |
| 2026-11-19 | Align compose.dev API publish port to 8000 | Match README and frontend env |
| 2026-11-19 | Document module boundaries without physical package split | Avoid sweeping refactor mid-reliability phase |
