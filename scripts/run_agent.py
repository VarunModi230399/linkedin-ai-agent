# scripts/run_agent.py
#
# Runs the full LinkedIn AI agent end to end.
# Uses MemorySaver for now — switches to PostgreSQL in Phase 8.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.checkpoint.memory import MemorySaver
from src.agent.graph.graph import build_agent_graph
from src.agent.graph.state import AgentState


def get_initial_state() -> dict:
    """Returns a clean initial state for a new agent run."""
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


def get_human_decision(state_values: dict) -> dict:
    """
    Shows the draft to the human and gets their decision.
    Returns the state update dict based on their choice.
    """
    print()
    print("=" * 60)
    print("⏸  AGENT PAUSED — Human approval required")
    print("=" * 60)
    print()

    # Show critique scores
    critique = state_values.get("critique", {})
    print("📊 Critique Scores:")
    print(f"   Hook:    {critique.get('hook', '?')}/10")
    print(f"   Value:   {critique.get('value', '?')}/10")
    print(f"   Voice:   {critique.get('voice', '?')}/10")
    print(f"   CTA:     {critique.get('cta', '?')}/10")
    print(f"   Length:  {critique.get('length', '?')}/10")
    print(f"   Overall: {state_values.get('critique_score', 0)}/10")
    print()

    # Show the draft
    print("📝 POST TO REVIEW:")
    print("-" * 60)
    print(state_values.get("draft", ""))
    print("-" * 60)
    print()
    print("What would you like to do?")
    print("  [a] Approve — publish as is")
    print("  [e] Edit    — approve with your changes")
    print("  [r] Reject  — send back for rewrite")
    print()

    while True:
        decision = input("Your decision (a/e/r): ").strip().lower()

        if decision == "a":
            print("✅ Post approved!")
            return {
                "approved": True,
                "human_feedback": "",
            }

        elif decision == "e":
            print()
            print("Paste your edited version.")
            print("Press Enter twice when done.")
            print()
            lines = []
            empty_count = 0
            while empty_count < 1:
                line = input()
                if line == "":
                    empty_count += 1
                else:
                    empty_count = 0
                    lines.append(line)

            edited = "\n".join(lines).strip()
            if edited:
                print("✅ Approved with your edits!")
                return {
                    "approved": True,
                    "draft": edited,
                    "human_feedback": (
                        f"Human edited. "
                        f"Original score: {state_values.get('critique_score')}"
                    ),
                }
            else:
                print("No edits detected — approving as is")
                return {
                    "approved": True,
                    "human_feedback": "",
                }

        elif decision == "r":
            print()
            feedback = input("What should be changed? ").strip()
            rejection_count = state_values.get("rejection_count", 0) + 1
            print(f"❌ Rejected (#{rejection_count}) — sending back for rewrite")
            return {
                "approved": False,
                "human_feedback": feedback,
                "rejection_count": rejection_count,
            }

        else:
            print("Please enter 'a', 'e', or 'r'")


def run_agent():
    print()
    print("=" * 60)
    print("🤖 LinkedIn AI Agent — Starting Run")
    print("=" * 60)
    print()

    # Build graph with MemorySaver checkpointer
    # Switches to PostgreSQL in Phase 8
    checkpointer = MemorySaver()
    graph = build_agent_graph(checkpointer=checkpointer)

    # Thread ID identifies this specific run
    # In production each run gets a unique UUID
    config = {"configurable": {"thread_id": "run_001"}}

    # Get fresh initial state
    state = get_initial_state()

    # ── Phase 1: Run until human_approval interrupt ──
    print("📍 Running pipeline until human approval...")
    print()

    try:
        for chunk in graph.stream(state, config=config):
            # Each chunk contains the node output
            # Nodes print their own progress — nothing needed here
            pass

    except Exception as e:
        print(f"❌ Pipeline error: {e}")
        raise

    # ── Get state at the interrupt point ────────────
    current = graph.get_state(config=config)
    state_values = current.values

    # Check if graph ended early due to error
    if state_values.get("error"):
        print(f"❌ Agent stopped with error: {state_values['error']}")
        return

    # ── Human decision ───────────────────────────────
    update = get_human_decision(state_values)

    # ── Phase 2: Resume after human decision ────────
    print()
    print("📍 Resuming agent after your decision...")
    print()

    # Push human decision into the graph state
    graph.update_state(config=config, values=update)

    # Resume — passing None resumes from checkpoint
    try:
        for chunk in graph.stream(None, config=config):
            pass

    except Exception as e:
        print(f"❌ Resume error: {e}")
        raise

    # ── Final summary ────────────────────────────────
    final = graph.get_state(config=config).values

    print()
    print("=" * 60)
    print("✅ AGENT RUN COMPLETE")
    print("=" * 60)
    print()
    print(f"  Pillar:         {final.get('pillar')}")
    print(f"  Selected idea:  {final.get('selected_idea', '')[:55]}")
    print(f"  Critique score: {final.get('critique_score')}/10")
    print(f"  Refinements:    {final.get('refinement_count')}")
    print(f"  Approved:       {final.get('approved')}")
    print(f"  Scheduled for:  {final.get('scheduled_for')}")
    print(f"  LinkedIn URN:   {final.get('linkedin_urn')}")
    print(f"  Error:          {final.get('error') or 'none'}")


if __name__ == "__main__":
    run_agent()
