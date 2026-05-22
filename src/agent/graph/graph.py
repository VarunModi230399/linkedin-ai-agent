# TODO: implement src/agent/graph/graph.py
# src/agent/graph/graph.py
#
# This is the central file that defines the entire agent.
# It wires all 11 nodes together into a LangGraph graph
# with conditional edges, the human approval interrupt,
# and PostgreSQL checkpointing for crash recovery.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from langgraph.graph import StateGraph, END
from src.agent.graph.state import AgentState

# ── Import all nodes ──────────────────────────────
from src.agent.nodes.ideation import (
    pick_pillar_node,
    generate_ideas_node,
    select_idea_node,
)
from src.agent.nodes.research import research_node
from src.agent.nodes.drafting import draft_node
from src.agent.nodes.critique import critique_node
from src.agent.nodes.refine import refine_node
from src.agent.nodes.human_approval import human_approval_node
from src.agent.nodes.schedule import schedule_node
from src.agent.nodes.publish import publish_node
from src.agent.nodes.track import track_node


# ── Conditional edge functions ────────────────────
# These functions look at the current state and return
# the name of the next node to run.


def route_after_critique(state: AgentState) -> str:
    """
    After critique — decide whether to refine or approve.

    Rules:
    - Score >= 7.0 AND refinements < 2 → human_approval
    - Score < 7.0 AND refinements < 2  → refine
    - Refinements >= 2                 → force human_approval
      (prevents infinite refine loops)
    """
    score = state.get("critique_score", 0.0)
    refinements = state.get("refinement_count", 0)

    if refinements >= 2:
        print("  ↪️  Max refinements reached — forcing to human_approval")
        return "human_approval"

    if score >= 7.0:
        print(f"  ↪️  Score {score} >= 7.0 — routing to human_approval")
        return "human_approval"

    print(f"  ↪️  Score {score} < 7.0 — routing to refine")
    return "refine"


def route_after_approval(state: AgentState) -> str:
    """
    After human approval — decide whether to publish or redraft.

    Rules:
    - Approved → schedule
    - Rejected AND rejection_count < 2 → draft (full rewrite)
    - Rejected AND rejection_count >= 2 → END (give up gracefully)
    """
    approved = state.get("approved", False)
    rejection_count = state.get("rejection_count", 0)

    if approved:
        print("  ↪️  Approved — routing to schedule")
        return "schedule"

    if rejection_count >= 2:
        print("  ↪️  Rejected twice — ending gracefully")
        return END

    print(f"  ↪️  Rejected (#{rejection_count}) — routing back to draft")
    return "draft"


# ── Build the graph ───────────────────────────────
def build_agent_graph() -> StateGraph:
    """
    Builds and compiles the full LangGraph agent.
    Returns the compiled graph ready to run.
    """
    # Create the graph with our state definition
    builder = StateGraph(AgentState)

    # ── Add all nodes ─────────────────────────────
    builder.add_node("pick_pillar", pick_pillar_node)
    builder.add_node("generate_ideas", generate_ideas_node)
    builder.add_node("select_idea", select_idea_node)
    builder.add_node("research", research_node)
    builder.add_node("draft", draft_node)
    builder.add_node("critique", critique_node)
    builder.add_node("refine", refine_node)
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("schedule", schedule_node)
    builder.add_node("publish", publish_node)
    builder.add_node("track", track_node)

    # ── Set entry point ───────────────────────────
    # This is the first node that runs
    builder.set_entry_point("pick_pillar")

    # ── Add normal edges (always go to next node) ─
    builder.add_edge("pick_pillar", "generate_ideas")
    builder.add_edge("generate_ideas", "select_idea")
    builder.add_edge("select_idea", "research")
    builder.add_edge("research", "draft")
    builder.add_edge("draft", "critique")
    builder.add_edge("refine", "critique")  # loop back
    builder.add_edge("schedule", "publish")
    builder.add_edge("publish", "track")
    builder.add_edge("track", END)

    # ── Add conditional edges ─────────────────────
    # After critique: refine OR human_approval
    builder.add_conditional_edges(
        "critique",
        route_after_critique,
        {
            "refine": "refine",
            "human_approval": "human_approval",
        },
    )

    # After human_approval: schedule OR draft OR END
    builder.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "schedule": "schedule",
            "draft": "draft",
            END: END,
        },
    )

    # ── Compile the graph ─────────────────────────
    # interrupt_before pauses execution at human_approval
    # so you can review before anything publishes
    graph = builder.compile(
        interrupt_before=["human_approval"],
    )

    print("✅ LangGraph agent compiled successfully")
    return graph


# ── Module-level graph instance ───────────────────
# Import this from other files to run the agent
agent_graph = build_agent_graph()
