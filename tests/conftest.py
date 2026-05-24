# TODO: implement tests/conftest.py
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_llm():
    """
    Mock LLM for testing nodes without real API calls.
    Saves money and makes tests fast and deterministic.

    Usage:
        def test_draft_node(mock_llm):
            mock_llm.invoke.return_value = MagicMock(content="test post")
    """
    mock = MagicMock()
    mock.invoke = MagicMock(return_value=MagicMock(content="mock response"))
    return mock


@pytest.fixture
def empty_state():
    """Returns a clean AgentState for testing individual nodes."""
    return {
        "pillar": "ai_tools",
        "ideas": [],
        "selected_idea": "",
        "research_results": [],
        "draft": "",
        "critique": {},
        "critique_score": 0.0,
        "refinement_count": 0,
        "approved": False,
        "human_feedback": "",
        "rejection_count": 0,
        "scheduled_for": "",
        "linkedin_urn": "",
        "error": "",
    }
