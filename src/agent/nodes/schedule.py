# src/agent/nodes/schedule.py
#
# Decides the optimal publish time for the approved post.
# LinkedIn engagement peaks Tue/Wed/Thu 8-10am.
# Stores the scheduled datetime in state for the publish node.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.agent.graph.state import AgentState
from datetime import datetime, timedelta
import pytz

# ── Config ────────────────────────────────────────
# Target timezone — set to your audience's timezone
# For a German-based account targeting European AI engineers:
TIMEZONE = "Europe/Berlin"

# Best days: 1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday
BEST_DAYS = [1, 2, 3]  # Tuesday=1, Wednesday=2, Thursday=3
# Note: Python weekday() returns 0=Monday, 1=Tuesday, 2=Wednesday...
BEST_DAYS_PYTHON = [1, 2, 3]  # Tuesday, Wednesday, Thursday

# Best hour to post (24h format)
BEST_HOUR = 9  # 9:00am
BEST_MINUTE = 0


def find_next_optimal_slot(now: datetime) -> datetime:
    """
    Find the next optimal posting slot from now.

    Rules:
    - Must be Tuesday, Wednesday, or Thursday
    - Must be at 9:00am in target timezone
    - Must be at least 1 hour from now
    - Never schedule on weekends
    """
    # Start checking from tomorrow to avoid same-day rushes
    # Unless it's early morning on a good day
    candidate = now.replace(
        hour=BEST_HOUR,
        minute=BEST_MINUTE,
        second=0,
        microsecond=0,
    )

    # If today is a good day and 9am hasn't passed yet
    # and we have at least 1 hour buffer — use today
    if now.weekday() in BEST_DAYS_PYTHON and candidate > now + timedelta(hours=1):
        return candidate

    # Otherwise find the next good day
    candidate = candidate + timedelta(days=1)

    # Keep advancing until we land on a good day
    # Max 7 iterations to avoid infinite loop
    for _ in range(7):
        if candidate.weekday() in BEST_DAYS_PYTHON:
            return candidate
        candidate += timedelta(days=1)

    # Fallback — return 2 days from now at 9am
    fallback = now + timedelta(days=2)
    return fallback.replace(
        hour=BEST_HOUR,
        minute=BEST_MINUTE,
        second=0,
        microsecond=0,
    )


# ── Node 9: schedule ──────────────────────────────
def schedule_node(state: AgentState) -> AgentState:
    """
    Determines the optimal publish time for the post.

    Only runs if approved=True.
    Finds next Tue/Wed/Thu at 9am in target timezone.

    Reads from state:
        - approved: must be True to proceed

    Updates state with:
        - scheduled_for: ISO datetime string
    """
    print("📅 schedule: finding optimal publish time...")

    # Safety check
    if not state.get("approved"):
        return {
            **state,
            "error": "schedule: post not approved — cannot schedule",
        }

    try:
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)

        optimal_slot = find_next_optimal_slot(now)

        # Ensure timezone info is attached
        if optimal_slot.tzinfo is None:
            optimal_slot = tz.localize(optimal_slot)

        # Format as ISO string for storage
        scheduled_for = optimal_slot.isoformat()

        # Human readable for logging
        readable = optimal_slot.strftime("%A %d %B %Y at %H:%M %Z")

        print(f"  ✅ Scheduled for: {readable}")
        print(f"  ISO format: {scheduled_for}")

        return {
            **state,
            "scheduled_for": scheduled_for,
            "error": "",
        }

    except Exception as e:
        error_msg = f"schedule node failed: {str(e)}"
        print(f"  ❌ {error_msg}")
        return {
            **state,
            "error": error_msg,
        }
