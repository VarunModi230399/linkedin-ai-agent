# src/agent/graph/graph.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from langgraph.graph import StateGraph, END
from src.agent.graph.state import AgentState

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


def route_after_critique(state: AgentState) -> str:
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


def build_agent_graph(checkpointer=None) -> StateGraph:
    """
    Builds and compiles the full LangGraph agent.
    Returns the compiled graph ready to run.
    """
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

    # ── Entry point ───────────────────────────────
    builder.set_entry_point("pick_pillar")

    # ── Normal edges ──────────────────────────────
    builder.add_edge("pick_pillar", "generate_ideas")
    builder.add_edge("generate_ideas", "select_idea")
    builder.add_edge("select_idea", "research")
    builder.add_edge("research", "draft")
    builder.add_edge("draft", "critique")
    builder.add_edge("refine", "critique")
    builder.add_edge("schedule", "publish")
    builder.add_edge("publish", "track")
    builder.add_edge("track", END)

    # ── Conditional edges ─────────────────────────
    builder.add_conditional_edges(
        "critique",
        route_after_critique,
        {
            "refine": "refine",
            "human_approval": "human_approval",
        },
    )
    builder.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "schedule": "schedule",
            "draft": "draft",
            END: END,
        },
    )

    # ── Checkpointer ──────────────────────────────
    if checkpointer is None:
        from langgraph.checkpoint.memory import MemorySaver

        checkpointer = MemorySaver()
        print("  ⚠️  Using MemorySaver — state lost on restart")
    else:
        print("  ✅ Using provided checkpointer")

    graph = builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_approval"],
    )

    print("✅ LangGraph agent compiled successfully")
    return graph
