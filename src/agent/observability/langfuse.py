# src/agent/observability/langfuse.py
#
# Langfuse v2 observability using direct SDK.
# Avoids LangChain callback version conflicts.
# Wraps LLM calls manually for full control.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.agent.core.settings import (
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
    LANGFUSE_HOST,
)


def get_langfuse_client():
    """
    Returns raw Langfuse v2 client.
    Used for creating traces and generations manually.
    """
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST,
        )
    except Exception as e:
        print(f"  ⚠️  Langfuse unavailable: {e}")
        return None


def trace_llm_call(
    trace_name: str,
    node_name: str,
    prompt: str,
    response_content: str,
    model: str,
    metadata: dict = None,
):
    """
    Manually traces a single LLM call to Langfuse.

    Call this AFTER every llm.invoke() to log:
    - The prompt sent
    - The response received
    - Which node/model was used
    - Any metadata (pillar, critique score etc.)

    Usage:
        response = llm.invoke(prompt)
        trace_llm_call(
            trace_name="agent_run",
            node_name="draft_node",
            prompt=prompt,
            response_content=response.content,
            model="gpt-4o",
            metadata={"pillar": state["pillar"]}
        )
    """
    try:
        from langfuse import Langfuse

        lf = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST,
        )

        # Create a trace for this agent run
        trace = lf.trace(
            name=trace_name,
            metadata=metadata or {},
        )

        # Log the generation (LLM call)
        trace.generation(
            name=node_name,
            model=model,
            input=prompt,
            output=response_content,
            metadata=metadata or {},
        )

        # Flush immediately so it appears in dashboard
        lf.flush()
        return True

    except Exception as e:
        print(f"  ⚠️  Tracing failed (non-critical): {e}")
        return False
