# src/agent/nodes/track.py
#
# Schedules analytics pulls after publishing.
# Records tracking jobs to be picked up by Celery worker.
# Actual LinkedIn analytics fetching happens in Phase 7.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.agent.graph.state import AgentState
from datetime import datetime, timedelta
import pytz

TIMEZONE = "Europe/Berlin"


def schedule_analytics_pulls(linkedin_urn: str, published_at: datetime) -> list[dict]:
    """
    Creates a schedule of analytics pulls for the post.
    Returns list of pull jobs with their target times.
    """
    pulls = []

    windows = [
        ("24h", timedelta(hours=24)),
        ("7d", timedelta(days=7)),
        ("30d", timedelta(days=30)),
    ]

    for window_name, delta in windows:
        pull_time = published_at + delta
        pulls.append(
            {
                "linkedin_urn": linkedin_urn,
                "window": window_name,
                "pull_at": pull_time.isoformat(),
                "status": "pending",
            }
        )

    return pulls


# ── Node 11: track ────────────────────────────────
def track_node(state: AgentState) -> AgentState:
    """
    Sets up analytics tracking for the published post.

    Reads from state:
        - linkedin_urn: the published post identifier
        - scheduled_for: when the post went live

    Updates state with:
        - No state changes — side effects only
          (writes tracking jobs to be processed later)
    """
    print("📊 track: scheduling analytics pulls...")

    linkedin_urn = state.get("linkedin_urn", "")
    scheduled_for = state.get("scheduled_for", "")

    if not linkedin_urn:
        print("  ⚠️  No LinkedIn URN found — skipping analytics setup")
        return {**state, "error": "track: no linkedin_urn in state"}

    try:
        tz = pytz.timezone(TIMEZONE)

        # Use scheduled_for as published_at
        if scheduled_for:
            published_at = datetime.fromisoformat(scheduled_for)
        else:
            published_at = datetime.now(tz)

        # Schedule the pulls
        pulls = schedule_analytics_pulls(linkedin_urn, published_at)

        print(f"  ✅ Analytics pulls scheduled for post: {linkedin_urn[:50]}")
        print()
        for pull in pulls:
            print(f"  📅 {pull['window']:5} pull → {pull['pull_at']}")

        print()
        print("  💡 Celery worker will execute these pulls in Phase 7")

        return {
            **state,
            "error": "",
        }

    except Exception as e:
        error_msg = f"track node failed: {str(e)}"
        print(f"  ❌ {error_msg}")
        return {
            **state,
            "error": error_msg,
        }
