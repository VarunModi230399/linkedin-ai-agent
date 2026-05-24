# TODO: implement src/agent/core/logging.py
# src/agent/core/logging.py
import structlog


def get_logger(name: str):
    """
    Returns a structured logger.
    Structured logging adds key=value pairs to every log line
    making it easy to search and filter in production.

    Usage:
        log = get_logger(__name__)
        log.info("draft_written", words=173, pillar="ai_tools")
    """
    return structlog.get_logger(name)
