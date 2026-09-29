from workers.app import celery_app
from workers.jobs.tasks import scrape_jobs_task


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Example: Run every 30 minutes. 
    # In a real app this could be dynamically driven from UserPreferences in the DB
    sender.add_periodic_task(
        1800.0, # 30 minutes
        scrape_jobs_task.s(
            sources=["remoteok", "arbeitnow", "himalayas", "jobicy"], 
            limit=20, 
            notify_matches=True
        ),
        name='scrape_public_sources_every_30m'
    )
