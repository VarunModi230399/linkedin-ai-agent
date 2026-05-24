# TODO: implement src/agent/core/exceptions.py
# src/agent/core/exceptions.py


class AgentError(Exception):
    """Base exception for all agent errors."""

    pass


class ResearchError(AgentError):
    """Raised when research node fails to find relevant content."""

    pass


class PublishError(AgentError):
    """Raised when LinkedIn API call fails."""

    pass


class ApprovalTimeoutError(AgentError):
    """Raised when human approval takes too long."""

    pass
