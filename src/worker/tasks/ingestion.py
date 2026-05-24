# TODO: implement src/worker/tasks/ingestion.py
# src/worker/tasks/ingestion.py
#
# Background tasks for knowledge base maintenance.
#
# Tasks:
#   refresh_knowledge_base  → daily fresh content ingestion
#   cleanup_old_chunks      → remove stale content weekly

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.worker.celery_app import celery_app
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@celery_app.task(
    bind=True,
    name="src.worker.tasks.ingestion.refresh_knowledge_base",
    max_retries=2,
    default_retry_delay=300,  # retry after 5 minutes
)
def refresh_knowledge_base(self):
    """
    Daily task: fetch fresh AI content and update knowledge base.
    Runs at 6am Europe/Berlin via Celery Beat.

    Uses the same seed script logic but as a background task.
    Deterministic IDs mean re-running never creates duplicates.
    """
    logger.info("Starting daily knowledge base refresh...")

    try:
        import asyncio
        from scripts.seed_knowledge_base import main as seed_main

        # Run the async ingestion pipeline
        asyncio.run(seed_main())

        logger.info("Knowledge base refresh completed successfully")
        return {"status": "success"}

    except Exception as exc:
        logger.error(f"Knowledge base refresh failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="src.worker.tasks.ingestion.cleanup_old_chunks",
)
def cleanup_old_chunks(self):
    """
    Weekly task: remove chunks older than 90 days.
    Keeps the knowledge base fresh and relevant.
    Old content naturally scores lower but wastes space.
    """
    logger.info("Starting weekly KB cleanup...")

    try:
        from src.agent.core.settings import QDRANT_URL
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, Range
        from datetime import datetime, timedelta

        client = QdrantClient(url=QDRANT_URL)
        cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

        # Scroll through and find old points
        # Note: Qdrant doesn't support date comparison natively
        # We filter by published_date string comparison
        old_points = []
        offset = None

        while True:
            results, offset = client.scroll(
                collection_name="knowledge_base",
                limit=100,
                offset=offset,
                with_payload=True,
            )

            for point in results:
                pub_date = point.payload.get("published_date", "")
                if pub_date and pub_date < cutoff:
                    old_points.append(point.id)

            if offset is None:
                break

        if old_points:
            client.delete(
                collection_name="knowledge_base",
                points_selector=old_points,
            )
            logger.info(f"Removed {len(old_points)} old chunks (before {cutoff})")
        else:
            logger.info("No old chunks to remove")

        return {"status": "success", "removed": len(old_points)}

    except Exception as exc:
        logger.error(f"KB cleanup failed: {exc}")
        raise self.retry(exc=exc)
