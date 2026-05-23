# TODO: implement src/worker/beat_schedule.py
# src/worker/beat_schedule.py
#
# Celery Beat schedule — defines WHEN tasks run.
# Beat is like cron but integrated with Celery.
#
# Schedule:
#   6:00am daily  → refresh knowledge base
#   Every 5 min   → check for scheduled posts to publish
#   Triggered     → analytics pulls (scheduled dynamically)

from celery.schedules import crontab
from src.worker.celery_app import celery_app

celery_app.conf.beat_schedule = {
    # ── Knowledge base refresh ────────────────────
    # Runs every morning at 6am Europe/Berlin time
    # Fetches latest AI news and papers
    "refresh-knowledge-base-daily": {
        "task": "src.worker.tasks.ingestion.refresh_knowledge_base",
        "schedule": crontab(hour=6, minute=0),
        "options": {"expires": 3600},  # expire if not run within 1 hour
    },
    # ── Check for posts to publish ────────────────
    # Runs every 5 minutes
    # Checks if any approved posts are due for publishing
    "check-scheduled-posts": {
        "task": "src.worker.tasks.publishing.check_and_publish_scheduled_posts",
        "schedule": crontab(minute="*/5"),
    },
    # ── Weekly KB cleanup ─────────────────────────
    # Every Sunday at 2am — removes chunks older than 90 days
    "weekly-kb-cleanup": {
        "task": "src.worker.tasks.ingestion.cleanup_old_chunks",
        "schedule": crontab(hour=2, minute=0, day_of_week=0),
    },
}
