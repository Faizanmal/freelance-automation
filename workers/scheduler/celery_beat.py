from workers.app import celery_app
from workers.jobs.tasks import (
    process_lead_digests_task,
    scrape_jobs_task,
    sweep_stale_jobs_task,
)


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Hunt clock: fill shared inventory with V1 spine + zero-cost HN source.
    sender.add_periodic_task(
        1800.0,  # 30 minutes
        scrape_jobs_task.s(
            sources=[
                "serpapi_freelance",
                "serpapi_jobs",
                "serpapi_companies",
                "hn_hiring",
            ],
            limit=25,
            notify_matches=False,
        ),
        name="scrape_v1_hunters_every_30m",
    )
    # Show clock: email digests on each user's schedule.
    sender.add_periodic_task(
        900.0,  # 15 minutes
        process_lead_digests_task.s(),
        name="lead_digests_every_15m",
    )
    # Stale sweeper: prune dead links and expired jobs exceeding TTL.
    sender.add_periodic_task(
        21600.0,  # 6 hours
        sweep_stale_jobs_task.s(max_stale_days=45, limit=200),
        name="sweep_stale_jobs_every_6h",
    )
