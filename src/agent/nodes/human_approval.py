# src/agent/nodes/human_approval.py
#
# The human approval node pauses the graph and
# waits for a human decision before publishing.
#
# In LangGraph this works via interrupt_before —
# the graph stops here and saves state to PostgreSQL.
# It resumes when the human makes a decision via API.
#
# For now we implement a CLI version for testing.
# The full FastAPI approval UI comes in Phase 6.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.agent.graph.state import AgentState


def human_approval_node(state: AgentState) -> AgentState:
    """
    Pauses execution for human review.

    In production: graph pauses here via LangGraph interrupt.
    The FastAPI approval UI sends the decision back.

    In testing: prompts the user in the terminal.

    Reads from state:
        - draft: the post to review
        - critique: scores for context
        - critique_score: overall quality score

    Updates state with:
        - approved: True or False
        - human_feedback: notes from reviewer
        - rejection_count: incremented if rejected
    """
    print()
    print("=" * 60)
    print("👤 HUMAN APPROVAL REQUIRED")
    print("=" * 60)
    print()
    print("📊 Critique Scores:")
    critique = state.get("critique", {})
    print(f"   Hook:   {critique.get('hook', '?')}/10")
    print(f"   Value:  {critique.get('value', '?')}/10")
    print(f"   Voice:  {critique.get('voice', '?')}/10")
    print(f"   CTA:    {critique.get('cta', '?')}/10")
    print(f"   Length: {critique.get('length', '?')}/10")
    print(f"   Overall: {state.get('critique_score', 0)}/10")
    print()
    print("📝 POST TO REVIEW:")
    print("-" * 60)
    print(state.get("draft", ""))
    print("-" * 60)
    print()
    print("What would you like to do?")
    print("  [a] Approve — publish as is")
    print("  [e] Edit    — approve with changes")
    print("  [r] Reject  — send back for rewrite")
    print()

    while True:
        decision = input("Your decision (a/e/r): ").strip().lower()

        if decision == "a":
            print("✅ Post approved!")
            return {
                **state,
                "approved": True,
                "human_feedback": "",
                "error": "",
            }

        elif decision == "e":
            print()
            print("Enter your edited version of the post.")
            print("(Paste your text, then press Enter twice when done)")
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

            edited_post = "\n".join(lines).strip()

            if edited_post:
                print()
                print("✅ Post approved with your edits!")
                return {
                    **state,
                    "approved": True,
                    "draft": edited_post,
                    "human_feedback": f"Human edited. Original score: {state.get('critique_score')}",
                    "error": "",
                }
            else:
                print("No edits detected — treating as approval")
                return {
                    **state,
                    "approved": True,
                    "human_feedback": "",
                    "error": "",
                }

        elif decision == "r":
            print()
            feedback = input("What should be changed? (brief note): ").strip()
            rejection_count = state.get("rejection_count", 0) + 1
            print(f"❌ Post rejected (rejection #{rejection_count})")
            return {
                **state,
                "approved": False,
                "human_feedback": feedback,
                "rejection_count": rejection_count,
                "error": "",
            }

        else:
            print("Please enter 'a', 'e', or 'r'")
