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

async def _scrape_jobs_async(sources: list[str], limit: int, notify_matches: bool, query: str | None = None):
    # Add fastapi dir to sys.path so we can import app
    import os
    import sys
    fastapi_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "fastapi"))
    if fastapi_dir not in sys.path:
        sys.path.insert(0, fastapi_dir)

    from backend.application.services.scrape_service import ScrapeService
    from database.core.session import get_session

    async with get_session() as session:
        service = ScrapeService(session)
        result = await service.run(sources, limit=limit, notify_matches=notify_matches, query=query)
        return result

@celery_app.task(name="tasks.scrape_jobs", bind=True)
def scrape_jobs_task(self, sources: list[str], limit: int, notify_matches: bool, query: str | None = None):
    """Background task to run scrapers."""
    result = _run_async(_scrape_jobs_async(sources, limit, notify_matches, query))
    return result

async def _enrich_job_async(job_id: int):
    import os
    import sys
    fastapi_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "fastapi"))
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
            metadata=job.tags and {"tags": job.tags} or {}
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

async def _send_notification_async(payload_dict: dict[str, Any]):
    import os
    import sys
    fastapi_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "fastapi"))
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
        destinations=payload_dict.get("destinations", {})
    )
    
    service = NotificationService()
    results = await service.dispatch(payload)
    return [{"channel": r.channel.value, "delivered": r.delivered, "error": r.error} for r in results]

@celery_app.task(name="tasks.send_notification", bind=True)
def send_notification_task(self, payload_dict: dict[str, Any]):
    """Background task to send a notification via Celery."""
    return _run_async(_send_notification_async(payload_dict))
