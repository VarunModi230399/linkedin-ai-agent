# TODO: implement tests/unit/test_critique.py
# tests/unit/test_critique.py
import pytest
from unittest.mock import MagicMock, patch


def test_critique_scores_above_threshold(empty_state):
    """Verify critique correctly identifies high quality posts."""
    empty_state["draft"] = "Strong hook. Specific numbers. Clear CTA. #AI"

    mock_response = '{"hook": 8, "value": 8, "voice": 7, "cta": 7, "length": 8, "feedback": "Good post"}'

    with patch("src.agent.nodes.critique.llm") as mock_llm:
        mock_llm.invoke.return_value = MagicMock(content=mock_response)
        from src.agent.nodes.critique import critique_node

        result = critique_node(empty_state)

    assert result["critique_score"] >= 7.0
    assert result["critique"]["hook"] == 8


def test_critique_scores_below_threshold(empty_state):
    """Verify critique correctly identifies weak posts."""
    empty_state["draft"] = "AI is good. Use AI. #AI"

    mock_response = '{"hook": 4, "value": 4, "voice": 5, "cta": 3, "length": 6, "feedback": "Too vague"}'

    with patch("src.agent.nodes.critique.llm") as mock_llm:
        mock_llm.invoke.return_value = MagicMock(content=mock_response)
        from src.agent.nodes.critique import critique_node

        result = critique_node(empty_state)

    assert result["critique_score"] < 7.0
