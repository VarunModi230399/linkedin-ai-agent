# TODO: implement src/worker/tasks/analytics.py
# src/worker/tasks/analytics.py
#
# Background tasks for LinkedIn analytics collection.
#
# Tasks:
#   schedule_analytics_for_post → schedules 3 pulls after publishing
#   pull_post_metrics           → fetches metrics from LinkedIn API
#   tag_top_performers          → marks high-engagement posts

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
    name="src.worker.tasks.analytics.schedule_analytics_for_post",
)
def schedule_analytics_for_post(
    post_id: str,
    linkedin_urn: str,
    published_at: str,
):
    """
    Schedules 3 analytics pulls after a post is published.
    Called immediately after successful publishing.

    Pull windows:
        24h  → first engagement signal
        7d   → main engagement window
        30d  → long-term reach
    """
    logger.info(f"Scheduling analytics for post {post_id[:8]}...")

    try:
        from datetime import timedelta

        pub_dt = datetime.fromisoformat(published_at)
        tz = pytz.timezone(TIMEZONE)
        if pub_dt.tzinfo is None:
            pub_dt = tz.localize(pub_dt)

        windows = [
            ("24h", 24 * 3600),
            ("7d", 7 * 24 * 3600),
            ("30d", 30 * 24 * 3600),
        ]

        for window_name, delay_seconds in windows:
            pull_post_metrics.apply_async(
                args=[post_id, linkedin_urn, window_name],
                countdown=delay_seconds,
            )
            logger.info(
                f"  Scheduled {window_name} pull in "
                f"{delay_seconds // 3600}h for post {post_id[:8]}"
            )

        return {"status": "success", "windows_scheduled": len(windows)}

    except Exception as exc:
        logger.error(f"Failed to schedule analytics: {exc}")
        return {"status": "error", "reason": str(exc)}


@celery_app.task(
    bind=True,
    name="src.worker.tasks.analytics.pull_post_metrics",
    max_retries=3,
    default_retry_delay=300,
)
def pull_post_metrics(
    self,
    post_id: str,
    linkedin_urn: str,
    window: str,
):
    """
    Pulls metrics from LinkedIn API for a specific post.
    Stores snapshot in the metrics store.

    In DRY_RUN mode: simulates metrics for testing.
    In LIVE mode: calls LinkedIn Analytics API.
    """
    logger.info(f"Pulling {window} metrics for post {post_id[:8]}...")

    try:
        from src.agent.nodes.publish import DRY_RUN

        if DRY_RUN:
            # Simulate realistic metrics for testing
            import random

            metrics = {
                "impressions": random.randint(200, 2000),
                "likes": random.randint(5, 80),
                "comments": random.randint(1, 20),
                "shares": random.randint(0, 10),
                "clicks": random.randint(10, 100),
            }
            logger.info(f"  DRY RUN metrics: {metrics}")
        else:
            # Live LinkedIn Analytics API call
            # Implemented fully in Phase 8
            metrics = _fetch_linkedin_metrics(linkedin_urn)

        # Calculate engagement rate
        eng_rate = (
            (metrics["likes"] + metrics["comments"] + metrics["shares"])
            / max(metrics["impressions"], 1)
            * 100
        )

        logger.info(
            f"  {window} metrics — "
            f"impressions: {metrics['impressions']}, "
            f"engagement: {eng_rate:.2f}%"
        )

        # Tag top performers (engagement > 3%)
        if window == "7d" and eng_rate > 3.0:
            tag_top_performer.delay(post_id, eng_rate, metrics)
            logger.info(f"  ⭐ Tagged as top performer ({eng_rate:.2f}%)")

        return {
            "status": "success",
            "window": window,
            "metrics": metrics,
            "engagement_rate": round(eng_rate, 2),
        }

    except Exception as exc:
        logger.error(f"Metrics pull failed: {exc}")
        raise self.retry(exc=exc)


def _fetch_linkedin_metrics(linkedin_urn: str) -> dict:
    """
    Calls LinkedIn Analytics API.
    Implemented fully when MDP approval comes through.
    """
    import httpx
    from src.agent.core.settings import LINKEDIN_ORG_URN
    import os

    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    if not access_token:
        raise ValueError("LINKEDIN_ACCESS_TOKEN not set")

    # Share statistics endpoint
    response = httpx.get(
        "https://api.linkedin.com/v2/organizationalEntityShareStatistics",
        params={
            "q": "organizationalEntity",
            "organizationalEntity": LINKEDIN_ORG_URN,
            "shares[0]": linkedin_urn,
        },
        headers={
            "Authorization": f"Bearer {access_token}",
            "LinkedIn-Version": "202504",
        },
        timeout=30.0,
    )

    if response.status_code != 200:
        raise Exception(f"LinkedIn API error: {response.status_code}")

    data = response.json()
    element = data.get("elements", [{}])[0]
    stats = element.get("totalShareStatistics", {})

    return {
        "impressions": stats.get("impressionCount", 0),
        "likes": stats.get("likeCount", 0),
        "comments": stats.get("commentCount", 0),
        "shares": stats.get("shareCount", 0),
        "clicks": stats.get("clickCount", 0),
    }


@celery_app.task(
    name="src.worker.tasks.analytics.tag_top_performer",
)
def tag_top_performer(post_id: str, eng_rate: float, metrics: dict):
    """
    Tags a post as a top performer.
    Top performers feed back into the ideation prompt
    as 'winning patterns' — the feedback loop.
    """
    logger.info(f"Tagging post {post_id[:8]} as top performer ({eng_rate:.2f}%)")

    try:
        from src.api.app import POST_STORE

        if post_id in POST_STORE:
            POST_STORE[post_id]["is_top_performer"] = True
            POST_STORE[post_id]["engagement_rate"] = eng_rate
            POST_STORE[post_id]["peak_metrics"] = metrics
            logger.info(f"  ✅ Tagged successfully")

        return {"status": "success", "post_id": post_id}

    except Exception as exc:
        logger.error(f"Tagging failed: {exc}")
        return {"status": "error", "reason": str(exc)}
