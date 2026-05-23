# scripts/run_agent.py
#
# Runs the full LinkedIn AI agent end to end.
# Submits post to FastAPI UI for approval.
# Polls API for human decision then resumes.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import httpx
from langgraph.checkpoint.memory import MemorySaver
from src.agent.graph.graph import build_agent_graph


def get_initial_state() -> dict:
    return {
        "pillar": "",
        "ideas": [],
        "selected_idea": "",
        "research_results": [],
        "draft": "",
        "critique": {},
        "critique_score": 0.0,
        "refinement_count": 0,
        "approved": False,
        "human_feedback": "",
        "rejection_count": 0,
        "scheduled_for": "",
        "linkedin_urn": "",
        "error": "",
    }


def submit_post_to_ui(state_values: dict) -> str:
    """
    Submits the generated post to the FastAPI approval UI.
    Returns the post_id for polling.
    """
    try:
        response = httpx.post(
            "http://localhost:8000/posts",
            json={
                "draft": state_values.get("draft", ""),
                "pillar": state_values.get("pillar", ""),
                "selected_idea": state_values.get("selected_idea", ""),
                "critique": state_values.get("critique", {}),
                "critique_score": state_values.get("critique_score", 0.0),
            },
            timeout=10.0,
        )
        data = response.json()
        return data["post_id"]
    except Exception as e:
        print(f"❌ Failed to submit post to UI: {e}")
        print(
            "   Make sure the API is running: uv run uvicorn src.api.app:app --reload --port 8000"
        )
        raise


def poll_for_decision(post_id: str, poll_interval: int = 5) -> dict:
    """
    Polls the API every poll_interval seconds until
    the human makes a decision (approve/reject/edit).
    Returns the decision dict.
    """
    print()
    print("=" * 60)
    print("⏸  Waiting for your approval decision...")
    print("=" * 60)
    print()
    print("   Open your browser at: http://localhost:8000")
    print(f"   Post ID: {post_id[:8]}...")
    print(f"   Polling every {poll_interval} seconds...")
    print()

    dots = 0
    while True:
        try:
            response = httpx.get(
                f"http://localhost:8000/posts/{post_id}/status",
                timeout=10.0,
            )
            data = response.json()
            status = data.get("status", "pending_approval")

            if status == "approved":
                print()
                print("✅ Post approved via browser!")
                return {
                    "approved": True,
                    "human_feedback": data.get("reviewer_notes", ""),
                }

            elif status == "approved_with_edit":
                print()
                print("✏️  Post approved with edits via browser!")
                return {
                    "approved": True,
                    "draft": data.get("content", ""),
                    "human_feedback": "Human edited via browser UI",
                }

            elif status == "rejected":
                print()
                print("❌ Post rejected via browser!")
                return {
                    "approved": False,
                    "human_feedback": data.get("reviewer_notes", "no feedback"),
                    "rejection_count": 1,
                }

            else:
                # Still pending — show waiting indicator
                dots = (dots + 1) % 4
                print(
                    f"\r   Waiting{'.' * dots}{'  ' * (3 - dots)}", end="", flush=True
                )
                time.sleep(poll_interval)

        except Exception as e:
            print(f"\n   ⚠️  Polling error: {e} — retrying...")
            time.sleep(poll_interval)


def run_agent():
    print()
    print("=" * 60)
    print("🤖 LinkedIn AI Agent — Starting Run")
    print("=" * 60)
    print()

    # Build graph with MemorySaver checkpointer
    checkpointer = MemorySaver()
    graph = build_agent_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "run_001"}}

    # Get fresh initial state
    state = get_initial_state()

    # ── Phase 1: Run until human_approval interrupt ──
    print("📍 Running pipeline until human approval...")
    print()

    try:
        for chunk in graph.stream(state, config=config):
            pass
    except Exception as e:
        print(f"❌ Pipeline error: {e}")
        raise

    # Get state at interrupt point
    current = graph.get_state(config=config)
    state_values = current.values

    if state_values.get("error"):
        print(f"❌ Agent stopped with error: {state_values['error']}")
        return

    # ── Submit post to UI for approval ──────────────
    print()
    print("📬 Submitting post to approval UI...")
    post_id = submit_post_to_ui(state_values)
    print(f"   ✅ Post submitted — ID: {post_id[:8]}...")

    # ── Poll for human decision ──────────────────────
    decision = poll_for_decision(post_id)

    # ── Phase 2: Resume with decision ───────────────
    print()
    print("📍 Resuming agent with your decision...")
    print()

    graph.update_state(config=config, values=decision)

    try:
        for chunk in graph.stream(None, config=config):
            pass
    except Exception as e:
        print(f"❌ Resume error: {e}")
        raise

    # Final summary
    final = graph.get_state(config=config).values

    print()
    print("=" * 60)
    print("✅ AGENT RUN COMPLETE")
    print("=" * 60)
    print()
    print(f"  Pillar:         {final.get('pillar')}")
    print(f"  Selected idea:  {final.get('selected_idea', '')[:55]}")
    print(f"  Critique score: {final.get('critique_score')}/10")
    print(f"  Approved:       {final.get('approved')}")
    print(f"  Scheduled for:  {final.get('scheduled_for')}")
    print(f"  LinkedIn URN:   {final.get('linkedin_urn')}")
    print(f"  Error:          {final.get('error') or 'none'}")


if __name__ == "__main__":
    run_agent()
