# src/agent/nodes/research.py
#
# The research node searches the Qdrant knowledge base
# for content relevant to the selected idea.
#
# Uses agentic RAG — evaluates result quality and
# retries with a different query if needed (max 3x).

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.agent.observability.langfuse import trace_llm_call
from src.agent.core.settings import OPENAI_API_KEY, OPENAI_MODEL_FAST
from src.agent.graph.state import AgentState
from src.agent.memory.vector_store import search_knowledge_base
from langchain_openai import ChatOpenAI

# ── LLM for query reformulation ───────────────────
llm = ChatOpenAI(
    model=OPENAI_MODEL_FAST,
    api_key=OPENAI_API_KEY,
    temperature=0.3,
)

# ── Relevance threshold ───────────────────────────
MIN_SCORE = 0.55
MAX_ATTEMPTS = 3


def generate_search_query(idea: str, attempt: int) -> str:
    """
    Generate a search query from the post idea.
    On retry attempts, reformulates to find better results.
    """
    if attempt == 0:
        return idea

    prompt = f"""You are helping search a knowledge base of AI news and research papers.

Original post idea: {idea}
This is search attempt #{attempt + 1} — previous attempts found low-relevance results.

Generate a SHORT search query (5-8 words) that will find relevant AI content.
Focus on the core technical topic, not the post angle.
Return ONLY the search query, nothing else."""

    response = llm.invoke(prompt)
    trace_llm_call(
        trace_name="agent_run",
        node_name="research_query_reformulation",
        prompt=prompt,
        response_content=response.content,
        model=OPENAI_MODEL_FAST,
        metadata={"attempt": attempt, "idea": idea[:50]},
    )
    return response.content.strip()


def evaluate_results(results: list[dict]) -> bool:
    """
    Check if search results are relevant enough to use.
    Returns True if good enough, False if we should retry.
    """
    if not results:
        return False

    best_score = results[0]["score"]

    if best_score < MIN_SCORE:
        print(
            f"  ⚠️  Best score {best_score:.3f} below threshold {MIN_SCORE} — retrying"
        )
        return False

    print(f"  ✅ Best score {best_score:.3f} meets threshold {MIN_SCORE}")
    return True


# ── Node 4: research ──────────────────────────────
def research_node(state: AgentState) -> AgentState:
    """
    Searches the knowledge base for content relevant
    to the selected idea using agentic RAG.

    Reads from state:
        - selected_idea: the idea chosen by select_idea

    Updates state with:
        - research_results: list of result dicts with
          text, title, url, author, published_date, publication
    """
    print("🔍 research: searching knowledge base...")
    print(f"   Idea: {state['selected_idea'][:60]}...")

    research_results = []
    found_good_results = False

    for attempt in range(MAX_ATTEMPTS):
        print(f"  Attempt {attempt + 1}/{MAX_ATTEMPTS}...")

        query = generate_search_query(state["selected_idea"], attempt)
        print(f"  Query: '{query}'")

        results = search_knowledge_base(query, top_k=5)

        if not results:
            print("  No results found — retrying...")
            continue

        for r in results[:3]:
            print(f"  Score: {r['score']:.3f} | {r['title'][:50]}")

        if evaluate_results(results):
            # Store full dicts — preserves citation metadata for draft node
            research_results = results
            found_good_results = True
            print(f"  ✅ Found {len(research_results)} relevant chunks")
            break
        else:
            print("  Results not relevant enough — reformulating query...")

    if not found_good_results:
        print("  ⚠️  All attempts below threshold — using best available results")
        print("  💡 Tip: add more content to knowledge base to improve scores")
        # Store full dicts — preserves citation metadata for draft node
        research_results = search_knowledge_base(state["selected_idea"], top_k=3)

    print(f"  ✅ Research complete — {len(research_results)} chunks ready")

    return {
        **state,
        "research_results": research_results,
        "error": "",
    }
