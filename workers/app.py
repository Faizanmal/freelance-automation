import os
import random

from celery import Celery
from celery.signals import beat_init, task_prerun, worker_ready

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
    # Bounded retries with jitter (tasks may still set max_retries).
    task_annotations={"*": {"retry_backoff": True, "retry_backoff_max": 600, "retry_jitter": True}},
)


@worker_ready.connect
def _on_worker_ready(**_kwargs):
    try:
        from workers.heartbeat import touch_worker

        touch_worker()
    except Exception:
        pass


@beat_init.connect
def _on_beat_init(**_kwargs):
    try:
        from workers.heartbeat import touch_beat

        touch_beat()
    except Exception:
        pass


@task_prerun.connect
def _on_task_prerun(**_kwargs):
    try:
        from workers.heartbeat import touch_worker

        touch_worker()
    except Exception:
        pass


def retry_countdown(base: int = 60, attempt: int = 0, cap: int = 600) -> int:
    """Exponential backoff with full jitter for manual self.retry(countdown=...)."""
    exp = min(cap, base * (2 ** max(attempt, 0)))
    return random.randint(1, max(1, exp))

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
