# TODO: implement src/agent/nodes/publish.py
# src/agent/nodes/publish.py
#
# Publishes the approved post to LinkedIn Company Page.
# Uses App 2 credentials (Community Management API).
#
# DRY_RUN=True simulates the API call without posting.
# Set DRY_RUN=False when MDP approval comes through.

import sys
from pathlib import Path
from src.agent.observability.db_writer import update_post_status

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.agent.core.settings import (
    LINKEDIN_PUBLISHER_CLIENT_ID,
    LINKEDIN_PUBLISHER_CLIENT_SECRET,
    LINKEDIN_ORG_URN,
)
from src.agent.graph.state import AgentState
import httpx
import os

# ── Config ────────────────────────────────────────
# Set to False when MDP approval comes through
DRY_RUN = True

# LinkedIn API config
LINKEDIN_API_BASE = "https://api.linkedin.com"
LINKEDIN_VERSION = "202504"


def build_post_payload(draft: str, org_urn: str) -> dict:
    """
    Build the LinkedIn API request payload.
    Follows the Posts API v2 schema exactly.
    """
    return {
        "author": org_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": draft},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }


async def post_to_linkedin(
    draft: str,
    access_token: str,
    org_urn: str,
) -> dict:
    """
    Makes the actual LinkedIn API call.
    Returns the response dict with post URN on success.
    """
    payload = build_post_payload(draft, org_urn)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{LINKEDIN_API_BASE}/rest/posts",
            headers={
                "Authorization": f"Bearer {access_token}",
                "LinkedIn-Version": LINKEDIN_VERSION,
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            json=payload,
            timeout=30.0,
        )

        if response.status_code == 201:
            # Success — extract post URN from response headers
            post_urn = response.headers.get("x-restli-id", "")
            return {
                "success": True,
                "post_urn": post_urn,
                "status_code": 201,
            }
        else:
            return {
                "success": False,
                "post_urn": "",
                "status_code": response.status_code,
                "error": response.text,
            }


# ── Node 10: publish ──────────────────────────────
def publish_node(state: AgentState) -> AgentState:
    """
    Publishes the post to LinkedIn Company Page.

    Reads from state:
        - draft: the approved post content
        - approved: must be True
        - scheduled_for: when it was meant to go out

    Updates state with:
        - linkedin_urn: the post URN after publishing
    """
    print("🚀 publish: sending post to LinkedIn...")

    # Safety checks
    if not state.get("approved"):
        return {
            **state,
            "error": "publish: post not approved",
        }

    if not state.get("draft"):
        return {
            **state,
            "error": "publish: no draft content found",
        }

    # ── DRY RUN MODE ──────────────────────────────
    if DRY_RUN:
        print()
        print("  🔶 DRY RUN MODE — not actually posting to LinkedIn")
        print("  (Set DRY_RUN=False when MDP approval comes through)")
        print()
        print("  What WOULD be posted:")
        print("  " + "-" * 50)
        print("  " + state["draft"][:200].replace("\n", "\n  "))
        print("  " + "-" * 50)
        print()

        # Simulate a successful response
        fake_urn = "urn:li:share:DRY_RUN_7234567890123456789"
        print(f"  ✅ Simulated post URN: {fake_urn}")

        # ← ADD HERE — inside DRY_RUN block
        if state.get("post_id"):
            update_post_status(
                post_id=state["post_id"],
                status="published",
                linkedin_urn=fake_urn,
                scheduled_for=state.get("scheduled_for", ""),
            )
            print("  📝 Post status updated in PostgreSQL")

        return {
            **state,
            "linkedin_urn": fake_urn,
            "error": "",
        }

    # ── LIVE MODE ─────────────────────────────────
    # Get access token from environment
    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")

    if not access_token:
        return {
            **state,
            "error": "publish: LINKEDIN_ACCESS_TOKEN not found in .env",
        }

    if not LINKEDIN_ORG_URN:
        return {
            **state,
            "error": "publish: LINKEDIN_ORG_URN not found in .env",
        }

    try:
        import asyncio

        result = asyncio.run(
            post_to_linkedin(
                draft=state["draft"],
                access_token=access_token,
                org_urn=LINKEDIN_ORG_URN,
            )
        )

        if result["success"]:
            print("  ✅ Post published successfully!")
            print(f"  URN: {result['post_urn']}")

            # Save to PostgreSQL — LIVE
            if state.get("post_id"):
                update_post_status(
                    post_id=state["post_id"],
                    status="published",
                    linkedin_urn=result["post_urn"],
                    scheduled_for=state.get("scheduled_for", ""),
                )
                print("  📝 Post status updated in PostgreSQL")

            return {
                **state,
                "linkedin_urn": result["post_urn"],
                "error": "",
            }
        else:
            error_msg = (
                f"LinkedIn API error {result['status_code']}: "
                f"{result.get('error', 'unknown')}"
            )
            print(f"  ❌ {error_msg}")
            return {
                **state,
                "error": error_msg,
            }

    except Exception as e:
        error_msg = f"publish node failed: {str(e)}"
        print(f"  ❌ {error_msg}")
        return {
            **state,
            "error": error_msg,
        }
