# TODO: implement src/agent/nodes/critique.py
# src/agent/nodes/critique.py
#
# The critique node evaluates the draft post quality.
# Uses a separate LLM call with a strict editor persona.
# This is the self-critique pattern used in production.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.agent.core.settings import OPENAI_API_KEY, OPENAI_MODEL
from src.agent.graph.state import AgentState
from langchain_openai import ChatOpenAI
import json
import re

# ── LLM Setup ─────────────────────────────────────
# GPT-4o for critique — needs strong reasoning
# to accurately evaluate post quality
llm = ChatOpenAI(
    model=OPENAI_MODEL,
    api_key=OPENAI_API_KEY,
    temperature=0.2,  # low temperature — we want consistent scoring
)


def parse_scores(response_text: str) -> dict:
    """
    Parse the JSON scores from the LLM response.
    Handles cases where the model adds extra text around the JSON.
    """
    # Try direct JSON parse first
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from within the response
    json_match = re.search(r"\{[^{}]+\}", response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Fallback — return neutral scores
    print("  ⚠️  Could not parse scores — using neutral fallback")
    return {
        "hook": 5,
        "value": 5,
        "voice": 5,
        "cta": 5,
        "length": 5,
        "feedback": "Could not parse critique scores",
    }


# ── Node 6: critique ──────────────────────────────
def critique_node(state: AgentState) -> AgentState:
    """
    Evaluates the draft post on 5 quality dimensions.
    Scores each 0-10. Average determines next step:
        >= 7.0 → human_approval
        <  7.0 → refine node

    Reads from state:
        - draft: the post written by draft node

    Updates state with:
        - critique: dict of scores per dimension
        - critique_score: average of all scores
    """
    print("🔍 critique: evaluating draft quality...")

    if not state.get("draft"):
        return {
            **state,
            "critique": {},
            "critique_score": 0.0,
            "error": "critique: no draft found in state",
        }

    prompt = f"""You are a harsh but fair LinkedIn content editor.
Your job is to evaluate posts for an AI engineer audience.
You have high standards — most posts need improvement.

Evaluate this LinkedIn post on exactly 5 dimensions.
Score each from 0-10 where:
    0-4  = poor, needs major work
    5-6  = mediocre, needs improvement
    7-8  = good, minor tweaks needed
    9-10 = excellent, publish as is

POST TO EVALUATE:
{state["draft"]}

SCORING CRITERIA:

hook (0-10):
- Does line 1 make you stop scrolling?
- Is it specific, surprising, or bold?
- Would an AI engineer want to read more?

value (0-10):
- Are there specific numbers, facts, or concrete details?
- Does the reader learn something actionable?
- Is it grounded in real experience?

voice (0-10):
- Does it sound like a real engineer (not marketing copy)?
- Is it first person and authentic?
- No buzzword soup or corporate speak?

cta (0-10):
- Is there a clear call to action?
- Is it specific (not just "like and share")?
- Does it invite genuine engagement?

length (0-10):
- Is it 150-250 words?
- Easy to read on mobile?
- No unnecessary padding?

Return ONLY a JSON object in this exact format:
{{
    "hook": <score>,
    "value": <score>,
    "voice": <score>,
    "cta": <score>,
    "length": <score>,
    "feedback": "<2-3 sentences on what to improve>"
}}

No other text. Just the JSON."""

    try:
        response = llm.invoke(prompt)
        scores = parse_scores(response.content)

        # Calculate average score
        score_values = [
            scores.get("hook", 5),
            scores.get("value", 5),
            scores.get("voice", 5),
            scores.get("cta", 5),
            scores.get("length", 5),
        ]
        avg_score = round(sum(score_values) / len(score_values), 2)

        print("  Scores:")
        print(f"    Hook:   {scores.get('hook')}/10")
        print(f"    Value:  {scores.get('value')}/10")
        print(f"    Voice:  {scores.get('voice')}/10")
        print(f"    CTA:    {scores.get('cta')}/10")
        print(f"    Length: {scores.get('length')}/10")
        print(f"  Average: {avg_score}/10")
        print(f"  Feedback: {scores.get('feedback', '')}")

        if avg_score >= 7.0:
            print("  ✅ Quality threshold met — routing to human approval")
        else:
            print(f"  ⚠️  Score {avg_score} below 7.0 — routing to refine")

        return {
            **state,
            "critique": scores,
            "critique_score": avg_score,
            "error": "",
        }

    except Exception as e:
        error_msg = f"critique node failed: {str(e)}"
        print(f"  ❌ {error_msg}")
        return {
            **state,
            "critique": {},
            "critique_score": 0.0,
            "error": error_msg,
        }
