import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "signaldesk_workers",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["workers.jobs.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    worker_concurrency=4,  # 4 parallel workers
)

from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    "scrape-v1-hunters-every-30m": {
        "task": "tasks.scrape_jobs",
        "schedule": 1800.0,  # every 30 minutes — fill shared job inventory
        "kwargs": {
            "sources": ["serpapi_freelance", "serpapi_jobs", "serpapi_companies"],
            "limit": 20,
            "notify_matches": False,
        },
    },
    "run-drip-campaign-daily": {
        "task": "tasks.process_drip_campaign",
        "schedule": crontab(hour=14, minute=0),  # Run daily at 14:00 UTC
    },
    "run-lead-digests-every-15m": {
        "task": "tasks.process_lead_digests",
        "schedule": 900.0,  # every 15 minutes — show-clock window check
    },
}
