# TODO: implement src/agent/nodes/drafting.py
# src/agent/nodes/drafting.py
#
# The draft node writes the actual LinkedIn post.
# It uses GPT-4o (not mini) because post quality
# directly impacts engagement and client acquisition.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.agent.core.settings import OPENAI_API_KEY, OPENAI_MODEL
from src.agent.graph.state import AgentState
from langchain_openai import ChatOpenAI

# ── LLM Setup ─────────────────────────────────────
# GPT-4o for drafting — quality matters here
# This is what the audience actually reads
llm = ChatOpenAI(
    model=OPENAI_MODEL,
    api_key=OPENAI_API_KEY,
    temperature=0.8,  # higher creativity for engaging posts
)

# ── Few-shot examples ─────────────────────────────
# These are examples of high-performing LinkedIn posts
# from AI engineers. The model learns style from these.
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


# ── Node 5: draft ─────────────────────────────────
def draft_node(state: AgentState) -> AgentState:
    """
    Writes a complete LinkedIn post using GPT-4o.

    Uses the selected idea and research results to
    produce a specific, engaging, high-quality post.

    Reads from state:
        - pillar: content category
        - selected_idea: the chosen post idea
        - research_results: relevant chunks from Qdrant
        - human_feedback: feedback if sent back from approval
        - draft: previous draft if this is a refinement

    Updates state with:
        - draft: the complete LinkedIn post text
    """
    print("✍️  draft: writing LinkedIn post...")
    print(f"   Idea: {state['selected_idea'][:60]}...")

    # Format research results for the prompt
    research_text = ""
    if state.get("research_results"):
        research_text = "\n\n".join(state["research_results"][:3])
    else:
        research_text = "No specific research available — use your general knowledge."

    # Include human feedback if this is a rewrite
    feedback_section = ""
    if state.get("human_feedback"):
        feedback_section = f"""
HUMAN REVIEWER FEEDBACK (incorporate this):
{state["human_feedback"]}

Previous draft that was rejected:
{state.get("draft", "")}
"""

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

Write ONLY the post. No title, no explanation, no preamble.
Start directly with the first line of the post."""

    try:
        response = llm.invoke(prompt)
        draft = response.content.strip()

        # Count words for logging
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
