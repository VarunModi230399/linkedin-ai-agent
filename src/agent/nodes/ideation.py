# TODO: implement src/agent/nodes/ideation.py
# src/agent/nodes/ideation.py
#
# This file contains 3 nodes:
#   1. pick_pillar    — choose content category
#   2. generate_ideas — create 5 post ideas
#   3. select_idea    — pick the best one
#
# We put them together because they are all
# part of the same "ideation" phase of the agent.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.agent.core.settings import OPENAI_API_KEY, OPENAI_MODEL_FAST
from src.agent.graph.state import AgentState
from langchain_openai import ChatOpenAI

# ── LLM Setup ─────────────────────────────────────
# We use gpt-4o-mini here — ideation does not need
# the full power of gpt-4o. Faster and 10x cheaper.
llm = ChatOpenAI(
    model=OPENAI_MODEL_FAST,
    api_key=OPENAI_API_KEY,
    temperature=0.7,  # some creativity for idea generation
)

# ── Content Pillars ───────────────────────────────
PILLARS = ["ai_tools", "case_study", "opinion", "tutorial"]


# ── Node 1: pick_pillar ───────────────────────────
def pick_pillar_node(state: AgentState) -> AgentState:
    """
    Picks the next content pillar using rotation strategy.

    Reads the last used pillar from state (if any),
    then picks the next one in the cycle.

    Updates state with:
        - pillar: the chosen content category
    """
    print("🎯 pick_pillar: choosing content category...")

    # Get the last used pillar from state
    # On first run, state.get returns None
    last_pillar = state.get("pillar", None)

    if last_pillar and last_pillar in PILLARS:
        # Move to the next pillar in rotation
        current_index = PILLARS.index(last_pillar)
        next_index = (current_index + 1) % len(PILLARS)
        chosen_pillar = PILLARS[next_index]
    else:
        # First run — start with ai_tools
        chosen_pillar = PILLARS[0]

    print(f"  ✅ Chosen pillar: {chosen_pillar}")

    # Return updated state — only change 'pillar'
    # All other state fields stay exactly as they were
    return {
        **state,  # keep everything else
        "pillar": chosen_pillar,
        "ideas": [],  # reset ideas for new run
        "error": "",  # clear any previous errors
    }


# ── Node 2: generate_ideas ────────────────────────
def generate_ideas_node(state: AgentState) -> AgentState:
    """
    Uses GPT-4o-mini to generate 5 post ideas for the chosen pillar.

    Reads from state:
        - pillar: the content category chosen by pick_pillar

    Updates state with:
        - ideas: list of 5 post ideas as strings
    """
    print(f"💡 generate_ideas: generating ideas for pillar '{state['pillar']}'...")

    # Pillar descriptions help the LLM understand context
    pillar_context = {
        "ai_tools": "showcasing or reviewing AI tools, APIs, and developer productivity",
        "case_study": "real-world AI implementation stories, results, and lessons learned",
        "opinion": "strong opinions and takes on AI trends, industry direction, and best practices",
        "tutorial": "step-by-step technical guides for building AI systems",
    }

    context = pillar_context.get(state["pillar"], "AI and machine learning topics")

    # The prompt — this is what gets sent to GPT-4o-mini
    prompt = f"""You are an AI engineer with 5 years of experience building production AI systems.
You write LinkedIn posts that get high engagement from a technical audience of developers,
ML engineers, and tech leads.

Generate exactly 5 LinkedIn post ideas for the category: {state["pillar"]}
Category focus: {context}

Requirements for each idea:
- Specific and concrete (not vague)
- Relevant to AI engineers and developers in 2026
- Has a clear angle (contrarian, how-to, lessons learned, or data-driven)
- Would make someone stop scrolling
- Maximum 15 words per idea

Return ONLY a numbered list like this:
1. idea one here
2. idea two here
3. idea three here
4. idea four here
5. idea five here

No explanations, no extra text, just the numbered list."""

    try:
        response = llm.invoke(prompt)
        raw_text = response.content

        # Parse the numbered list into a clean Python list
        ideas = []
        for line in raw_text.strip().split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                # Remove the number and period/dot at the start
                # "1. My idea here" → "My idea here"
                idea = line.split(".", 1)[-1].strip()
                if idea:
                    ideas.append(idea)

        # Safety check — if parsing failed, use raw lines
        if not ideas:
            ideas = [l.strip() for l in raw_text.split("\n") if l.strip()]

        # Keep only first 5
        ideas = ideas[:5]

        print(f"  ✅ Generated {len(ideas)} ideas")
        for i, idea in enumerate(ideas, 1):
            print(f"     {i}. {idea}")

        return {
            **state,
            "ideas": ideas,
            "error": "",
        }

    except Exception as e:
        error_msg = f"generate_ideas failed: {str(e)}"
        print(f"  ❌ {error_msg}")
        return {
            **state,
            "ideas": [],
            "error": error_msg,
        }


# ── Node 3: select_idea ───────────────────────────
def select_idea_node(state: AgentState) -> AgentState:
    """
    Picks the single best idea from the generated list.

    Uses GPT-4o-mini to evaluate all 5 ideas and select
    the one most likely to get high engagement on LinkedIn
    from an AI engineer audience.

    Reads from state:
        - ideas: list of 5 ideas from generate_ideas
        - pillar: content category for context

    Updates state with:
        - selected_idea: the single chosen idea string
    """
    print("🎯 select_idea: picking the best idea...")

    # Safety check — if no ideas, return error
    if not state.get("ideas"):
        return {
            **state,
            "selected_idea": "",
            "error": "select_idea: no ideas in state to select from",
        }

    # Format ideas as numbered list for the prompt
    ideas_text = "\n".join(f"{i + 1}. {idea}" for i, idea in enumerate(state["ideas"]))

    prompt = f"""You are an expert LinkedIn content strategist for AI engineers.

Here are 5 LinkedIn post ideas for the category: {state["pillar"]}

{ideas_text}

Your audience: software engineers, ML engineers, tech leads, AI consultants.
Goal: maximum engagement (likes, comments, shares) from this technical audience.

Evaluate each idea on:
- Hook strength (does it make you stop scrolling?)
- Specificity (concrete vs vague)
- Relevance to AI engineers in 2026
- Novelty (fresh angle vs overdone topic)

Return ONLY the text of the single best idea.
No explanation, no number, no extra text.
Just the idea itself."""

    try:
        response = llm.invoke(prompt)
        selected = response.content.strip()

        # Clean up whatever the model added around the idea
        # Only strip if it matches "1." or "2)" pattern — not if number is part of idea
        import re

        # Matches: "1. text" or "1) text" — list prefixes only
        list_prefix_pattern = re.compile(r"^\d+[\.\)]\s+")
        if list_prefix_pattern.match(selected):
            selected = list_prefix_pattern.sub("", selected).strip()

        # Remove surrounding quotes the model sometimes adds
        selected = selected.strip('"').strip("'").strip()

        print(f"  ✅ Selected idea: {selected}")

        return {
            **state,
            "selected_idea": selected,
            "error": "",
        }

    except Exception as e:
        # Fallback — just pick the first idea if LLM fails
        fallback = state["ideas"][0]
        error_msg = f"select_idea LLM failed, using fallback: {str(e)}"
        print(f"  ⚠️  {error_msg}")
        print(f"  📌 Fallback idea: {fallback}")

        return {
            **state,
            "selected_idea": fallback,
            "error": error_msg,
        }
