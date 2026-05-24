# src/agent/nodes/drafting.py
#
# The draft node writes the actual LinkedIn post.
# Uses GPT-4o for quality — this is what people read.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.agent.observability.langfuse import trace_llm_call
from src.agent.core.settings import OPENAI_API_KEY, OPENAI_MODEL
from src.agent.graph.state import AgentState
from langchain_openai import ChatOpenAI

# ── LLM Setup ─────────────────────────────────────
llm = ChatOpenAI(
    model=OPENAI_MODEL,
    api_key=OPENAI_API_KEY,
    temperature=0.8,
)

# ── Few-shot examples ─────────────────────────────
FEW_SHOT_EXAMPLES = """
EXAMPLE 1 (ai_tools pillar — 8,200 impressions):
I built an AI agent that writes LinkedIn posts automatically.

Here's what surprised me after 47 posts:

- GPT-4o drafts better hooks than I do (embarrassing but true)
- Tuesday 9am = 3x more impressions than Friday afternoon
- Posts about failures outperform success stories every time
- The system costs $0.67/month to run

The uncomfortable truth: consistency beats quality.

I shipped 3 posts/week for 90 days. Engagement compounded.

Now I get 2-3 inbound leads per month from LinkedIn alone.

Want to build something similar? DM me "agent" and I'll share the architecture.

#AIEngineering #LLMOps #Automation

---

EXAMPLE 2 (opinion pillar — 6,100 impressions):
Unpopular opinion: Most AI agents in production are just expensive if/else statements.

I've reviewed 40+ "AI agent" implementations in the last 6 months.

Here's what I actually found:

- 60% were single LLM calls with no real agency
- 25% had loops but no state management
- 10% were genuinely agentic (LangGraph, multi-step reasoning)
- 5% were production-ready with evals, observability, fallbacks

The bar is low. That's good news for engineers who do it properly.

What separates real agents from fake ones? Three things:
1. Persistent state across steps
2. Conditional branching based on output quality
3. Human-in-the-loop for high-stakes decisions

Build these three things and you're already in the top 10%.

#AIAgents #MLEngineering #SoftwareEngineering

---

EXAMPLE 3 (tutorial pillar — 5,400 impressions):
How to set up RAG in under 30 minutes (the right way):

Most tutorials skip the part that actually matters.

Step 1: Don't use naive RAG
→ Single vector search fails 40% of the time
→ Use hybrid search (BM25 + dense vectors)

Step 2: Chunk properly
→ 512 tokens with 10% overlap
→ Semantic chunking beats fixed-size every time

Step 3: Add a reranker
→ Cross-encoder after retrieval
→ Cuts irrelevant results by 60%

Step 4: Eval before shipping
→ Ragas framework, 20 test questions
→ Faithfulness > 0.9 is your target

I use this stack: Qdrant + BGE-M3 + bge-reranker-v2-m3

Total cost: $0 (all open source, runs locally)

Save this for your next RAG project.

#RAG #LLM #AIEngineering
"""


def draft_node(state: AgentState) -> AgentState:
    """
    Writes a complete LinkedIn post using GPT-4o.

    Reads from state:
        - pillar, selected_idea, research_results
        - human_feedback (if rewrite)

    Updates state with:
        - draft: the complete post text
    """
    print("✍️  draft: writing LinkedIn post...")
    print(f"   Idea: {state['selected_idea'][:60]}...")

    # ── Format research results ───────────────────
    # research_results are dicts from search_knowledge_base
    # Each has: text, title, url, author, published_date, publication
    research_text = ""
    if state.get("research_results"):
        formatted_sources = []
        for r in state["research_results"][:3]:
            if isinstance(r, dict):
                # Build citation from metadata
                citation_parts = []
                if r.get("publication"):
                    citation_parts.append(r["publication"])
                if r.get("author"):
                    citation_parts.append(f"by {r['author']}")
                if r.get("published_date"):
                    citation_parts.append(r["published_date"])

                citation = (
                    " — ".join(citation_parts) if citation_parts else "AI Research"
                )
                url = r.get("url", "")
                text = r.get("text", "")

                formatted_sources.append(f"[Source: {citation}]\nURL: {url}\n{text}")
            else:
                # Fallback — research_result is a plain string
                formatted_sources.append(str(r))

        research_text = "\n\n---\n\n".join(formatted_sources)
    else:
        research_text = "No specific research available — use your general knowledge."

    # ── Include human feedback if rewrite ────────
    feedback_section = ""
    if state.get("human_feedback"):
        feedback_section = f"""
HUMAN REVIEWER FEEDBACK (incorporate this):
{state["human_feedback"]}

Previous draft that was rejected:
{state.get("draft", "")}
"""

    # ── Build prompt ──────────────────────────────
    prompt = f"""You are an AI engineer with 5 years of production experience.
You write LinkedIn posts that get high engagement from technical audiences.

Here are examples of your best performing posts:
{FEW_SHOT_EXAMPLES}

Now write a NEW LinkedIn post with these exact specifications:

POST IDEA: {state["selected_idea"]}
CONTENT PILLAR: {state["pillar"]}

RELEVANT RESEARCH (use this to add specific facts and credibility):
{research_text}
{feedback_section}

STRICT REQUIREMENTS:
1. Start with a STRONG hook — first line must make someone stop scrolling
2. Use first person voice ("I", "my", "I built", "I learned")
3. Include specific numbers or concrete details (not vague claims)
4. Use short paragraphs or bullet points — easy to read on mobile
5. End with ONE clear CTA (call to action)
6. Add 3-5 relevant hashtags on the last line
7. Total length: 150-250 words maximum
8. NO corporate speak, NO buzzword soup
9. Sound like a real engineer sharing real experience
10. CITATION RULE: When using information from research sources,
    reference naturally: 'According to a recent arXiv paper...'
    or 'As reported by Dev.to this week...'
    End with: 'Source links in comments 👇'

Write ONLY the post. No title, no explanation, no preamble.
Start directly with the first line of the post."""

    try:
        response = llm.invoke(prompt)

        # ── Trace to Langfuse ─────────────────────
        trace_llm_call(
            trace_name="agent_run",
            node_name="draft",
            prompt=prompt,
            response_content=response.content,
            model=OPENAI_MODEL,
            metadata={
                "pillar": state.get("pillar", ""),
                "selected_idea": state.get("selected_idea", "")[:50],
                "refinement_count": state.get("refinement_count", 0),
            },
        )

        draft = response.content.strip()
        word_count = len(draft.split())

        print(f"  ✅ Draft written — {word_count} words")
        print()
        print("  --- DRAFT PREVIEW ---")
        print(draft[:300] + "..." if len(draft) > 300 else draft)
        print("  --- END PREVIEW ---")

        return {
            **state,
            "draft": draft,
            "error": "",
        }

    except Exception as e:
        error_msg = f"draft node failed: {str(e)}"
        print(f"  ❌ {error_msg}")
        return {
            **state,
            "draft": "",
            "error": error_msg,
        }
