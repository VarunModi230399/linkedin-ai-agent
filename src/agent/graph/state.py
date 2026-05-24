# TODO: implement src/agent/graph/state.py
# src/agent/graph/state.py
#
# AgentState is the single source of truth that flows
# through every node in the LangGraph pipeline.
#
# Think of it as the relay baton — each node reads it,
# updates its relevant fields, and passes it forward.

from typing import TypedDict


class AgentState(TypedDict):
    # ── Phase 1: Topic Selection ───────────────────
    pillar: str
    # Which content category we are writing about.
    # Options: "ai_tools" | "case_study" | "opinion" | "tutorial"
    # Set by: pick_pillar node

    # ── Phase 2: Idea Generation ───────────────────
    ideas: list[str]
    # List of 5 post ideas generated for the pillar.
    # Example: ["5 ways GPT-4o saves time", "Why RAG matters in 2026"]
    # Set by: generate_ideas node

    selected_idea: str
    # The single best idea chosen from the ideas list.
    # This becomes the focus of the entire post.
    # Set by: select_idea node

    # ── Phase 3: Research ──────────────────────────
    research_results: list[dict]
    # Relevant chunks retrieved from Qdrant knowledge base.
    # These ground the post in real, current information.
    # Set by: research node

    # ── Phase 4: Drafting ──────────────────────────
    draft: str
    # The full LinkedIn post text written by the LLM.
    # Gets updated each time the refine node runs.
    # Set by: draft node, updated by: refine node

    # ── Phase 5: Critique ──────────────────────────
    critique: dict
    # Scores from the self-critique node.
    # Structure: {"hook": 8, "value": 7, "voice": 9, "cta": 6, "length": 8}
    # Each score is 0-10. Average becomes critique_score.
    # Set by: critique node

    critique_score: float
    # Average of all critique scores.
    # If < 7.0 → send to refine node
    # If >= 7.0 → send to human_approval node
    # Set by: critique node

    refinement_count: int
    # Tracks how many times the draft has been refined.
    # Safety limit: max 2 refinements then force to human_approval.
    # Prevents infinite refine loops.
    # Set by: refine node

    # ── Phase 6: Human Approval ────────────────────
    approved: bool
    # Whether the human approved the post.
    # True → proceed to schedule + publish
    # False → send back to draft node
    # Set by: human_approval node

    human_feedback: str
    # Optional feedback from the human reviewer.
    # Used by the refine node if post is sent back.
    # Set by: human_approval node

    # Add this field to AgentState — it tracks the approval decision
    rejection_count: int
    # How many times this post has been rejected by human
    # Used to prevent infinite rejection loops

    # ── Phase 7: Publishing ────────────────────────
    scheduled_for: str
    # ISO datetime string for when to publish.
    # Example: "2026-05-27T09:00:00+02:00"
    # Set by: schedule node

    linkedin_urn: str
    # The LinkedIn post URN after successful publishing.
    # Example: "urn:li:share:7234567890123456789"
    # Used for analytics tracking later.
    # Set by: publish node

    # ── Error Handling ─────────────────────────────
    error: str
    # Stores error message if any node fails.
    # Empty string means no error.
    # Set by: any node that catches an exception

    # Add this field to AgentState
    post_id: str
    # PostgreSQL ID for this post
    # Set by: draft node
    # Used by: critique, approval, publish nodes
