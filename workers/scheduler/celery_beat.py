from workers.app import celery_app
from workers.jobs.tasks import process_lead_digests_task, scrape_jobs_task


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Hunt clock: fill shared inventory.
    sender.add_periodic_task(
        1800.0,  # 30 minutes
        scrape_jobs_task.s(
            sources=["serpapi_freelance", "serpapi_jobs", "serpapi_companies"],
            limit=20,
            notify_matches=False,
        ),
        name="scrape_v1_hunters_every_30m",
    )
    # Show clock: email digests on each user's schedule.
    sender.add_periodic_task(
        900.0,
        process_lead_digests_task.s(),
        name="lead_digests_every_15m",
    )
