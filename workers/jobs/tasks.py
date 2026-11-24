import asyncio
from typing import Any

from workers.app import celery_app


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        # If we're already in an event loop (unlikely in Celery, but possible if configured weirdly)
        import nest_asyncio

        nest_asyncio.apply()
        return asyncio.run(coro)
    else:
        return loop.run_until_complete(coro)


import json
import logging
import uuid
from datetime import UTC

from celery import Task

from workers.app import retry_countdown
from workers.locks import overlap_lock

logger = logging.getLogger(__name__)


class DLQTask(Task):
    """Base task that pushes failed executions to a Redis Dead Letter Queue after all retries are exhausted."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        super().on_failure(exc, task_id, args, kwargs, einfo)
        import os
        import sys

        fastapi_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "fastapi")
        )
        if fastapi_dir not in sys.path:
            sys.path.insert(0, fastapi_dir)

        from app.core.redis_client import get_redis

        async def push_to_dlq():
            redis_client = await get_redis()
            if redis_client:
                import datetime as dt

                dlq_entry = {
                    "task_id": task_id,
                    "task_name": self.name,
                    "run_id": (kwargs or {}).get("run_id"),
                    "args": args,
                    "kwargs": {
                        k: v
                        for k, v in (kwargs or {}).items()
                        if k not in {"password", "token", "secret"}
                    },
                    "exception": str(exc),
                    "traceback": str(einfo),
                    "failed_at": dt.datetime.now(dt.UTC).isoformat(),
                }
                await redis_client.lpush("celery_dlq", json.dumps(dlq_entry))
                logger.error(
                    "Task %s failed permanently; queued to DLQ run_id=%s",
                    self.name,
                    dlq_entry.get("run_id"),
                )

        _run_async(push_to_dlq())


async def _scrape_jobs_async(
    sources: list[str], limit: int, notify_matches: bool, query: str | None = None
):
    # Add fastapi dir to sys.path so we can import app
    import os
    import sys

    fastapi_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "fastapi")
    )
    if fastapi_dir not in sys.path:
        sys.path.insert(0, fastapi_dir)

    from backend.application.services.scrape_service import ScrapeService
    from database.core.session import get_session

    async with get_session() as session:
        service = ScrapeService(session)
        result = await service.run(
            sources, limit=limit, notify_matches=notify_matches, query=query
        )
        return result


@celery_app.task(name="tasks.touch_heartbeat")
def touch_heartbeat_task():
    """Keep worker + beat readiness keys fresh between 30m scrapes."""
    try:
        from workers.heartbeat import touch_beat, touch_worker

        touch_worker()
        touch_beat()
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("touch_heartbeat failed: %s", exc.__class__.__name__)
        return {"status": "error", "error": exc.__class__.__name__}


@celery_app.task(
    name="tasks.scrape_jobs",
    bind=True,
    base=DLQTask,
    max_retries=3,
    default_retry_delay=60,
)
def scrape_jobs_task(
    self,
    sources: list[str],
    limit: int,
    notify_matches: bool,
    query: str | None = None,
    run_id: str | None = None,
):
    """Background task to run scrapers (overlap-locked; idempotent per run_id)."""
    run_id = run_id or str(uuid.uuid4())
    with overlap_lock("scrape_jobs", ttl_seconds=max(300, limit * 15)) as acquired:
        if not acquired:
            logger.info("scrape_jobs skipped (overlap lock) run_id=%s", run_id)
            return {"status": "skipped", "reason": "overlap_lock", "run_id": run_id}
        try:
            try:
                from workers.heartbeat import touch_beat, touch_worker

                touch_worker()
                touch_beat()
            except Exception:
                pass
            result = _run_async(
                _scrape_jobs_async(sources, limit, notify_matches, query)
            )
            if isinstance(result, dict):
                result = {**result, "run_id": run_id}
            return result
        except (RuntimeError, TimeoutError) as exc:
            raise self.retry(
                exc=exc, countdown=retry_countdown(60, self.request.retries)
            )


async def _enrich_job_async(job_id: int):
    import os
    import sys

    fastapi_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "fastapi")
    )
    if fastapi_dir not in sys.path:
        sys.path.insert(0, fastapi_dir)

    from backend.application.services.duplicate_detection import JobCandidate
    from backend.application.services.enrichment import EnrichmentService
    from database.core.session import get_session
    from database.models.job import JobRecord

    async with get_session() as session:
        job = await session.get(JobRecord, job_id)
        if not job:
            return None

        candidate = JobCandidate(
            source_name=job.source_name,
            source_id=job.source_id,
            title=job.title,
            description=job.description,
            url=job.url,
            company=job.company,
            budget_min=job.budget_min,
            budget_max=job.budget_max,
            posted_at=job.posted_at,
            metadata=(job.tags and {"tags": job.tags}) or {},
        )

        service = EnrichmentService()
        enrichment = await service.enrich(candidate)

        job.enrichment = enrichment.to_dict()
        job.seniority = enrichment.seniority
        job.analysis_summary = enrichment.summary

        await session.commit()
        return job.id


@celery_app.task(name="tasks.enrich_job", bind=True)
def enrich_jobs_task(self, job_id: int):
    """Background task to enrich a job."""
    return _run_async(_enrich_job_async(job_id))


async def _reindex_embeddings_async(limit: int = 200, force: bool = False):
    import os
    import sys

    fastapi_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "fastapi")
    )
    if fastapi_dir not in sys.path:
        sys.path.insert(0, fastapi_dir)

    from backend.application.services.ranking.embeddings import EmbeddingIndex
    from backend.infrastructure.repositories.job_repository import SQLAlchemyJobRepository
    from database.core.session import get_session

    async with get_session() as session:
        repo = SQLAlchemyJobRepository(session)
        jobs = await repo.list_recent(limit=max(1, min(int(limit), 500)))
        index = EmbeddingIndex()
        await index.persist_dirty(
            session,
            jobs,
            batch_limit=min(64, len(jobs) or 1),
            budget_ms=5000,
            force=force,
        )
        return index.metrics_dict() | {
            "limit": limit,
            "force": force,
            "status": "ok",
        }


@celery_app.task(
    name="tasks.reindex_embeddings",
    bind=True,
    base=DLQTask,
    max_retries=2,
    default_retry_delay=30,
)
def reindex_embeddings_task(self, limit: int = 200, force: bool = False):
    """Background safe reindex of job embedding vectors (content-hash keyed)."""
    try:
        return _run_async(_reindex_embeddings_async(limit=limit, force=force))
    except (RuntimeError, TimeoutError) as exc:
        raise self.retry(
            exc=exc, countdown=retry_countdown(30, self.request.retries)
        )


async def _send_notification_async(payload_dict: dict[str, Any]):
    import os
    import sys

    fastapi_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "fastapi")
    )
    if fastapi_dir not in sys.path:
        sys.path.insert(0, fastapi_dir)

    from backend.application.services.notification_service import (
        NotificationChannel,
        NotificationPayload,
        NotificationPriority,
        NotificationService,
    )

    # Reconstruct payload
    channels = [NotificationChannel(c) for c in payload_dict.get("channels", [])]
    priority = NotificationPriority(payload_dict.get("priority", "normal"))

    payload = NotificationPayload(
        user_id=payload_dict.get("user_id", "system"),
        title=payload_dict.get("title", ""),
        body=payload_dict.get("body", ""),
        channels=channels,
        priority=priority,
        digest=payload_dict.get("digest", False),
        ai_summary=payload_dict.get("ai_summary"),
        destinations=payload_dict.get("destinations", {}),
    )

    service = NotificationService()
    results = await service.dispatch(payload)
    return [
        {"channel": r.channel.value, "delivered": r.delivered, "error": r.error}
        for r in results
    ]


@celery_app.task(
    name="tasks.send_notification",
    bind=True,
    base=DLQTask,
    max_retries=3,
    default_retry_delay=60,
)
def send_notification_task(self, payload_dict: dict[str, Any], run_id: str | None = None):
    """Background task to send a notification via Celery."""
    run_id = run_id or str(uuid.uuid4())
    payload = {**(payload_dict or {}), "run_id": run_id}
    try:
        return _run_async(_send_notification_async(payload))
    except (RuntimeError, TimeoutError) as exc:
        raise self.retry(exc=exc, countdown=retry_countdown(60, self.request.retries))


DRIP_STEPS = (
    (
        1,
        "Set your first Signal Desk keywords",
        "You signed up yesterday. Open Preferences and add the skills you want alerts for. Alerts only go out after your email is verified.",
    ),
    (
        3,
        "Get more freelance leads with Signal Desk Pro",
        "Pro unlocks premium sources plus higher API limits. If the free matches are close but not enough, upgrade from the Pricing page.",
    ),
    (
        7,
        "One week on Signal Desk",
        "If the desk is quiet, widen your keywords or drop an exclude term that is filtering too much. Pro users also get the marketplace sources.",
    ),
)


async def _process_drip_campaign_async():
    import os
    import sys
    from datetime import datetime, timedelta

    fastapi_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "fastapi")
    )
    if fastapi_dir not in sys.path:
        sys.path.insert(0, fastapi_dir)

    from sqlalchemy import select

    from database.core.session import get_session
    from database.models.user import User

    now = datetime.now(UTC)
    sent = 0
    async with get_session() as session:
        for days, title, body in DRIP_STEPS:
            window_end = now - timedelta(days=days)
            window_start = now - timedelta(days=days + 1)
            result = await session.execute(
                select(User).where(
                    User.plan == "free",
                    User.is_active.is_(True),
                    User.created_at <= window_end,
                    User.created_at > window_start,
                )
            )
            users = result.scalars().all()
            for user in users:
                send_notification_task.delay(
                    {
                        "user_id": str(user.id),
                        "title": title,
                        "body": f"Hi {user.full_name or 'there'},\n\n{body}\n\nThe Signal Desk Team",
                        "channels": ["email"],
                        "priority": "normal",
                    }
                )
                sent += 1
        return f"Queued drip emails for {sent} users."


@celery_app.task(
    name="tasks.process_drip_campaign",
    bind=True,
    base=DLQTask,
    max_retries=3,
    default_retry_delay=60,
)
def process_drip_campaign_task(self, run_id: str | None = None):
    """Daily sequence for free users: day 1, day 3, and day 7."""
    run_id = run_id or str(uuid.uuid4())
    with overlap_lock("process_drip_campaign", ttl_seconds=3600) as acquired:
        if not acquired:
            return {"status": "skipped", "reason": "overlap_lock", "run_id": run_id}
        try:
            from workers.heartbeat import touch_beat

            touch_beat()
            result = _run_async(_process_drip_campaign_async())
            return {"result": result, "run_id": run_id}
        except (RuntimeError, TimeoutError) as exc:
            raise self.retry(
                exc=exc, countdown=retry_countdown(60, self.request.retries)
            )


async def _process_lead_digests_async():
    import os
    import sys

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    fastapi_dir = os.path.join(root, "fastapi")
    for path in (root, fastapi_dir):
        if path not in sys.path:
            sys.path.insert(0, path)

    from backend.application.services.digest_service import DigestService
    from database.core.session import get_session

    async with get_session() as session:
        return await DigestService(session).process_due_digests()


@celery_app.task(
    name="tasks.process_lead_digests",
    bind=True,
    base=DLQTask,
    max_retries=3,
    default_retry_delay=60,
)
def process_lead_digests_task(self, run_id: str | None = None):
    """Show-clock digests: send when user local day/time window matches."""
    run_id = run_id or str(uuid.uuid4())
    with overlap_lock("process_lead_digests", ttl_seconds=840) as acquired:
        if not acquired:
            return {"status": "skipped", "reason": "overlap_lock", "run_id": run_id}
        try:
            from workers.heartbeat import touch_beat

            touch_beat()
            result = _run_async(_process_lead_digests_async())
            return {"result": result, "run_id": run_id}
        except (RuntimeError, TimeoutError) as exc:
            raise self.retry(
                exc=exc, countdown=retry_countdown(60, self.request.retries)
            )


async def _process_outbox_async(batch_size: int = 50):
    import os
    import sys

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    fastapi_dir = os.path.join(root, "fastapi")
    for path in (root, fastapi_dir):
        if path not in sys.path:
            sys.path.insert(0, path)

    from backend.application.services.outbox_service import OutboxService
    from database.core.session import get_session

    async with get_session() as session:
        return await OutboxService(session).process_pending_outbox(
            batch_size=batch_size
        )


@celery_app.task(
    name="tasks.process_outbox",
    bind=True,
    base=DLQTask,
    max_retries=3,
    default_retry_delay=30,
)
def process_outbox_task(self, batch_size: int = 50, run_id: str | None = None):
    """Processes pending transactional outbox notifications with bounded retries."""
    run_id = run_id or str(uuid.uuid4())
    with overlap_lock("process_outbox", ttl_seconds=120) as acquired:
        if not acquired:
            return {"status": "skipped", "reason": "overlap_lock", "run_id": run_id}
        try:
            from workers.heartbeat import touch_beat

            touch_beat()
            result = _run_async(_process_outbox_async(batch_size=batch_size))
            return {"result": result, "run_id": run_id}
        except (RuntimeError, TimeoutError) as exc:
            raise self.retry(
                exc=exc, countdown=retry_countdown(30, self.request.retries)
            )


async def _sweep_stale_jobs_async(max_stale_days: int = 45, limit: int = 200) -> int:
    import os
    import sys

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    fastapi_dir = os.path.join(root, "fastapi")
    for path in (root, fastapi_dir):
        if path not in sys.path:
            sys.path.insert(0, path)

    from backend.application.services.job_expiration import JobExpirationService
    from database.core.session import get_session

    async with get_session() as session:
        service = JobExpirationService(session)
        return await service.sweep_stale_jobs(
            max_stale_days=max_stale_days, limit=limit
        )


@celery_app.task(
    name="tasks.sweep_stale_jobs",
    bind=True,
    base=DLQTask,
    max_retries=3,
    default_retry_delay=60,
)
def sweep_stale_jobs_task(
    self, max_stale_days: int = 45, limit: int = 200, run_id: str | None = None
):
    """Background task to sweep and expire jobs exceeding TTL."""
    run_id = run_id or str(uuid.uuid4())
    with overlap_lock("sweep_stale_jobs", ttl_seconds=1800) as acquired:
        if not acquired:
            return {"status": "skipped", "reason": "overlap_lock", "run_id": run_id}
        try:
            expired = _run_async(
                _sweep_stale_jobs_async(max_stale_days=max_stale_days, limit=limit)
            )
            return {"expired": expired, "run_id": run_id}
        except (RuntimeError, TimeoutError) as exc:
            raise self.retry(
                exc=exc, countdown=retry_countdown(60, self.request.retries)
            )
