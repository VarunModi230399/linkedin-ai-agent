# TODO: implement tests/unit/test_drafting.py
# tests/unit/test_drafting.py
import pytest
from unittest.mock import MagicMock, patch


def test_draft_node_produces_content(empty_state):
    """Verify draft node writes something into state.draft."""
    empty_state["selected_idea"] = "5 ways GPT-4o saves developers time"
    empty_state["pillar"] = "ai_tools"
    empty_state["research_results"] = [
        {
            "text": "GPT-4o has batch API",
            "title": "OpenAI",
            "url": "",
            "author": "",
            "published_date": "",
            "publication": "",
            "score": 0.5,
        }
    ]

    with patch("src.agent.nodes.drafting.llm") as mock_llm:
        mock_llm.invoke.return_value = MagicMock(
            content="🚀 5 ways GPT-4o saved me 10 hours last week..."
        )
        from src.agent.nodes.drafting import draft_node

        result = draft_node(empty_state)

    assert len(result["draft"]) > 50
    assert result["error"] == ""


def test_draft_node_handles_llm_failure(empty_state):
    """Verify draft node handles exceptions gracefully."""
    empty_state["selected_idea"] = "test idea"
    empty_state["pillar"] = "ai_tools"

    with patch("src.agent.nodes.drafting.llm") as mock_llm:
        mock_llm.invoke.side_effect = Exception("API timeout")
        from src.agent.nodes.drafting import draft_node

        result = draft_node(empty_state)

    assert result["draft"] == ""
    assert "failed" in result["error"]
