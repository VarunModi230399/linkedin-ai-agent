# TODO: implement src/agent/nodes/refine.py
# src/agent/nodes/refine.py
#
# The refine node rewrites the draft based on critique feedback.
# Called when critique_score < 7.0
# Maximum 2 refinement attempts then forces to human_approval.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.agent.core.settings import OPENAI_API_KEY, OPENAI_MODEL
from src.agent.graph.state import AgentState
from langchain_openai import ChatOpenAI

# ── LLM Setup ─────────────────────────────────────
# GPT-4o for refining — same quality level as drafting
llm = ChatOpenAI(
    model=OPENAI_MODEL,
    api_key=OPENAI_API_KEY,
    temperature=0.7,
)


# ── Node 7: refine ────────────────────────────────
def refine_node(state: AgentState) -> AgentState:
    """
    Rewrites the draft based on critique feedback.

    Reads from state:
        - draft: the current post draft
        - critique: scores and feedback from critique node
        - refinement_count: how many times refined so far
        - selected_idea: original idea for context
        - pillar: content category

    Updates state with:
        - draft: the improved post
        - refinement_count: incremented by 1
    """
    current_count = state.get("refinement_count", 0)
    print(f"✏️  refine: improving draft (attempt {current_count + 1}/2)...")

    # Extract what needs fixing from critique
    critique = state.get("critique", {})
    feedback = critique.get("feedback", "Improve overall quality")

    # Build specific improvement instructions from scores
    improvements = []

    if critique.get("hook", 10) < 7:
        improvements.append(
            "HOOK: Rewrite the first line to be more bold, "
            "specific, or surprising. Make it impossible to scroll past."
        )

    if critique.get("value", 10) < 7:
        improvements.append(
            "VALUE: Add more specific numbers, concrete examples, "
            "or actionable insights. Avoid vague claims."
        )

    if critique.get("voice", 10) < 7:
        improvements.append(
            "VOICE: Make it sound more like a real engineer sharing "
            "genuine experience. More first person, less marketing speak."
        )

    if critique.get("cta", 10) < 7:
        improvements.append(
            "CTA: Replace the call to action with something more specific "
            "and engaging. Ask a real question or offer something concrete."
        )

    if critique.get("length", 10) < 7:
        improvements.append(
            "LENGTH: Adjust to 150-250 words. Cut padding, "
            "keep only the most valuable content."
        )

    improvements_text = "\n".join(f"- {imp}" for imp in improvements)

    prompt = f"""You are an expert LinkedIn ghostwriter for AI engineers.

You need to improve this LinkedIn post based on specific feedback.

ORIGINAL POST:
{state["draft"]}

CRITIQUE SCORES:
- Hook:   {critique.get("hook", "?")}/10
- Value:  {critique.get("value", "?")}/10
- Voice:  {critique.get("voice", "?")}/10
- CTA:    {critique.get("cta", "?")}/10
- Length: {critique.get("length", "?")}/10

EDITOR FEEDBACK:
{feedback}

SPECIFIC IMPROVEMENTS NEEDED:
{improvements_text if improvements_text else "Polish and improve overall quality"}

POST CONTEXT:
- Original idea: {state.get("selected_idea", "")}
- Content pillar: {state.get("pillar", "")}

REWRITE RULES:
1. Keep the core message and structure
2. Fix ONLY the weak areas identified above
3. Keep strong parts exactly as they are
4. Maintain 150-250 word count
5. First person voice throughout
6. End with a stronger CTA
7. Keep the hashtags at the end

Write ONLY the improved post.
No explanation, no preamble, just the post."""

    try:
        response = llm.invoke(prompt)
        improved_draft = response.content.strip()
        word_count = len(improved_draft.split())

        print(f"  ✅ Draft refined — {word_count} words")
        print()
        print("  --- REFINED DRAFT PREVIEW ---")
        print(
            improved_draft[:300] + "..."
            if len(improved_draft) > 300
            else improved_draft
        )
        print("  --- END PREVIEW ---")

        return {
            **state,
            "draft": improved_draft,
            "refinement_count": current_count + 1,
            "error": "",
        }

    except Exception as e:
        error_msg = f"refine node failed: {str(e)}"
        print(f"  ❌ {error_msg}")
        return {
            **state,
            "refinement_count": current_count + 1,
            "error": error_msg,
        }
