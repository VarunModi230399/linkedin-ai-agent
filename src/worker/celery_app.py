# TODO: implement src/worker/celery_app.py
# src/worker/celery_app.py
#
# Celery application instance and configuration.
# All background tasks import from this module.
#
# Broker:  Redis (already running in Docker)
# Backend: Redis (stores task results)

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from celery import Celery
from src.agent.core.settings import REDIS_URL

# ── Create Celery app ─────────────────────────────
celery_app = Celery(
    "linkedin_agent",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "src.worker.tasks.ingestion",  # KB refresh
        "src.worker.tasks.analytics",  # LinkedIn metrics
        "src.worker.tasks.publishing",  # Scheduled publishing
    ],
)

# ── Configuration ─────────────────────────────────
celery_app.conf.update(
    # Timezone
    timezone="Europe/Berlin",
    enable_utc=True,
    # Task settings
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Retry settings
    task_max_retries=3,
    task_default_retry_delay=60,  # 60 seconds between retries
    # Result expiry — keep results for 24 hours
    result_expires=86400,
    # Prevent tasks from running too long
    task_soft_time_limit=300,  # 5 min soft limit
    task_time_limit=600,  # 10 min hard limit
)

if __name__ == "__main__":
    celery_app.start()
