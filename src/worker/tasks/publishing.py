# TODO: implement src/worker/tasks/publishing.py
# src/worker/tasks/publishing.py
#
# Background tasks for scheduled post publishing.
#
# Tasks:
#   check_and_publish_scheduled_posts → runs every 5 min
#   publish_single_post               → publishes one post

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.worker.celery_app import celery_app
from celery.utils.log import get_task_logger
from datetime import datetime
import pytz

logger = get_task_logger(__name__)
TIMEZONE = "Europe/Berlin"


@celery_app.task(
    bind=True,
    name="src.worker.tasks.publishing.check_and_publish_scheduled_posts",
)
def check_and_publish_scheduled_posts(self):
    """
    Runs every 5 minutes.
    Checks if any approved posts are due for publishing.
    In production: queries PostgreSQL for due posts.
    In development: checks the in-memory POST_STORE.
    """
    logger.info("Checking for scheduled posts due for publishing...")

    try:
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)

        # Import the in-memory store from the API
        # In Phase 8 this switches to PostgreSQL query
        from src.api.app import POST_STORE

        due_posts = []
        for post_id, post in POST_STORE.items():
            if post["status"] not in ("approved", "approved_with_edit"):
                continue

            scheduled_for = post.get("scheduled_for")
            if not scheduled_for:
                continue

            # Parse scheduled time
            try:
                scheduled_dt = datetime.fromisoformat(scheduled_for)
                if scheduled_dt.tzinfo is None:
                    scheduled_dt = tz.localize(scheduled_dt)
            except Exception:
                continue

            # Check if it is time to publish
            if now >= scheduled_dt:
                due_posts.append(post_id)

        if due_posts:
            logger.info(f"Found {len(due_posts)} posts due for publishing")
            for post_id in due_posts:
                publish_single_post.delay(post_id)
        else:
            logger.info("No posts due for publishing")

        return {"status": "success", "due_posts": len(due_posts)}

    except Exception as exc:
        logger.error(f"Check scheduled posts failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="src.worker.tasks.publishing.publish_single_post",
    max_retries=3,
    default_retry_delay=60,
)
def publish_single_post(self, post_id: str):
    """
    Publishes a single approved post to LinkedIn.
    Called by check_and_publish_scheduled_posts when due.

    Uses idempotency check — safe to retry.
    """
    logger.info(f"Publishing post {post_id[:8]}...")

    try:
        from src.api.app import POST_STORE
        from src.agent.nodes.publish import publish_node

        post = POST_STORE.get(post_id)
        if not post:
            logger.error(f"Post {post_id} not found")
            return {"status": "error", "reason": "not_found"}

        # Idempotency check — don't publish twice
        if post.get("status") == "published":
            logger.info(f"Post {post_id[:8]} already published — skipping")
            return {"status": "skipped", "reason": "already_published"}

        # Build minimal state for publish node
        state = {
            "draft": post["content"],
            "approved": True,
            "scheduled_for": post.get("scheduled_for", ""),
            "linkedin_urn": "",
            "error": "",
        }

        # Call publish node
        result = publish_node(state)

        if result.get("error"):
            raise Exception(result["error"])

        # Update post status
        POST_STORE[post_id]["status"] = "published"
        POST_STORE[post_id]["linkedin_urn"] = result.get("linkedin_urn", "")

        logger.info(
            f"Post {post_id[:8]} published — URN: {result.get('linkedin_urn', '')[:30]}"
        )

        # Schedule analytics pulls
        from src.worker.tasks.analytics import schedule_analytics_for_post

        schedule_analytics_for_post.delay(
            post_id=post_id,
            linkedin_urn=result.get("linkedin_urn", ""),
            published_at=datetime.now(pytz.timezone(TIMEZONE)).isoformat(),
        )

        return {"status": "success", "linkedin_urn": result.get("linkedin_urn")}

    except Exception as exc:
        logger.error(f"Publish failed for {post_id[:8]}: {exc}")
        raise self.retry(exc=exc)
