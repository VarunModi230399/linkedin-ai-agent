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
