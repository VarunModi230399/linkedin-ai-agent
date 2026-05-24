# TODO: implement evals/run_evals.py
# evals/run_evals.py
#
# Run quality evaluations on the agent pipeline.
# Execute before any prompt change to detect regressions.
#
# Usage: uv run python evals/run_evals.py

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Eval dataset — real ideas with expected quality bars
EVAL_CASES = [
    {
        "pillar": "ai_tools",
        "idea": "5 ways GPT-4o API saves developers 10 hours weekly",
        "min_score": 7.0,
        "must_contain": ["hook", "CTA"],
    },
    {
        "pillar": "opinion",
        "idea": "Why most AI agents fail in production",
        "min_score": 7.0,
        "must_contain": ["specific", "experience"],
    },
]


def run_evals():
    from src.agent.nodes.drafting import draft_node
    from src.agent.nodes.critique import critique_node

    passed = 0
    failed = 0

    for case in EVAL_CASES:
        print(f"Evaluating: {case['idea'][:50]}...")

        # Build test state
        state = {
            "pillar": case["pillar"],
            "selected_idea": case["idea"],
            "research_results": [],
            "draft": "",
            "critique": {},
            "critique_score": 0.0,
            "refinement_count": 0,
            "approved": False,
            "human_feedback": "",
            "rejection_count": 0,
            "ideas": [],
            "scheduled_for": "",
            "linkedin_urn": "",
            "error": "",
        }

        state = draft_node(state)
        state = critique_node(state)

        if state["critique_score"] >= case["min_score"]:
            print(f"  ✅ PASS — score {state['critique_score']}/10")
            passed += 1
        else:
            print(
                f"  ❌ FAIL — score {state['critique_score']}/10 (need {case['min_score']})"
            )
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_evals()
    sys.exit(0 if success else 1)
