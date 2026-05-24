# scripts/run_agent.py
import sys
from pathlib import Path
import uuid
from src.agent.observability.db_writer import (
    save_agent_run,
    complete_agent_run,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import httpx
from src.agent.graph.graph import build_agent_graph


def get_initial_state() -> dict:
    return {
        "pillar": "",
        "ideas": [],
        "selected_idea": "",
        "post_id": "",
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


def get_checkpointer():
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from src.agent.core.settings import DATABASE_URL
        import psycopg

        sync_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

        # autocommit=True required for CREATE INDEX CONCURRENTLY
        conn = psycopg.connect(sync_url, autocommit=True)
        checkpointer = PostgresSaver(conn)
        checkpointer.setup()
        print("✅ Using PostgreSQL checkpointer — state survives restarts")
        return checkpointer

    except Exception as e:
        print(f"⚠️  PostgreSQL checkpointer failed: {e}")
        print("   Falling back to MemorySaver")
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()


def submit_post_to_ui(state_values: dict) -> str:
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
        return response.json()["post_id"]
    except Exception as e:
        print(f"❌ Failed to submit post to UI: {e}")
        print(
            "   Make sure API is running: uv run uvicorn src.api.app:app --reload --port 8000"
        )
        raise


def poll_for_decision(post_id: str, poll_interval: int = 5) -> dict:
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

    # Generate unique run ID for this session
    run_id = str(uuid.uuid4())

    # Save run start to PostgreSQL
    save_agent_run(run_id)
    print(f"  📝 Run ID: {run_id[:8]}... saved to PostgreSQL")

    # ── Checkpointer ──────────────────────────────
    checkpointer = get_checkpointer()
    graph = build_agent_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "run_001"}}
    state = get_initial_state()

    # ── Phase 1: Run until human_approval ─────────
    print("📍 Running pipeline until human approval...")
    print()

    try:
        for chunk in graph.stream(state, config=config):
            pass
    except Exception as e:
        print(f"❌ Pipeline error: {e}")
        raise

    current = graph.get_state(config=config)
    state_values = current.values

    if state_values.get("error"):
        print(f"❌ Agent stopped with error: {state_values['error']}")
        return

    # ── Submit to UI ───────────────────────────────
    print()
    print("📬 Submitting post to approval UI...")
    post_id = submit_post_to_ui(state_values)
    print(f"   ✅ Post submitted — ID: {post_id[:8]}...")

    # ── Poll for decision ──────────────────────────
    decision = poll_for_decision(post_id)

    # ── Phase 2: Resume ────────────────────────────
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

    # ── Final summary ──────────────────────────────
    final = graph.get_state(config=config).values

    # Mark run as complete in PostgreSQL
    complete_agent_run(
        run_id=run_id,
        status="completed" if not final.get("error") else "failed",
        error=final.get("error", ""),
    )
    print("  📝 Run saved to PostgreSQL")

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
