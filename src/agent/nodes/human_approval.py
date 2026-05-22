# src/agent/nodes/human_approval.py
#
# The human approval node is an interrupt point in LangGraph.
# It does NOT handle user input directly — that happens in
# run_agent.py after the graph pauses.
#
# This node simply marks the interrupt location.
# LangGraph pauses here via interrupt_before=["human_approval"]
# The runner script handles the human interaction then resumes.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.agent.graph.state import AgentState


def human_approval_node(state: AgentState) -> AgentState:
    """
    Interrupt point for human review.

    When LangGraph hits this node it has already been
    interrupted by interrupt_before=["human_approval"].
    The human decision has been injected via update_state()
    in run_agent.py before this node runs on resume.

    Simply passes the state through — the approved/rejected
    decision is already in state from the runner script.
    """
    print("👤 human_approval: processing decision...")

    approved = state.get("approved", False)
    if approved:
        print("  ✅ Post approved by human")
    else:
        feedback = state.get("human_feedback", "no feedback")
        print(f"  ❌ Post rejected — feedback: {feedback}")

    return {**state}
