# scripts/seed_knowledge_base.py
import sys
from pathlib import Path
import hashlib
import asyncio
import httpx
import xml.etree.ElementTree as ET

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import from central settings — loads correct .env automatically
from src.agent.core.settings import OPENAI_API_KEY, QDRANT_URL

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

# ── Config ────────────────────────────────────────
COLLECTION_NAME = "knowledge_base"
EMBEDDING_MODEL = "text-embedding-3-large"

openai_client = OpenAI(api_key=OPENAI_API_KEY)
qdrant_client = QdrantClient(url=QDRANT_URL)


# ── Deterministic ID (prevents duplicates) ────────
def generate_deterministic_id(text: str) -> str:
    """Same text always produces same ID — prevents duplicates in Qdrant."""
    return hashlib.md5(text.encode()).hexdigest()


# ── Step 1a: Fetch from Hacker News ───────────────
async def fetch_hn_ai_stories(limit: int = 10) -> list[dict]:
    print(f"📡 Fetching top {limit} AI stories from Hacker News...")
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(
                "https://hn.algolia.com/api/v1/search",
                params={
                    "query": "artificial intelligence machine learning LLM",
                    "tags": "story",
                    "hitsPerPage": limit,
                },
            )

            if response.status_code != 200:
                print(f"⚠️ HN returned status {response.status_code} — skipping")
                return []

            data = response.json()
            stories = []
            for hit in data.get("hits", []):
                title = hit.get("title", "")
                url = hit.get("url", "")
                # HN comments/discussion text is richer than story_text
                story_text = hit.get("story_text") or ""
                comment_text = hit.get("comment_text") or ""

                # Combine all available text
                full_text = f"{title}. {story_text} {comment_text}".strip()

                if title and len(full_text) > 50:
                    stories.append(
                        {
                            "title": title,
                            "url": url,
                            "text": full_text,
                            "source": "hackernews",
                        }
                    )

            print(f"✅ Fetched {len(stories)} HN stories")
            return stories

    except Exception as e:
        print(f"⚠️ HN fetch failed: {e} — skipping")
        return []


# ── Step 1b: Fetch from arXiv ─────────────────────
async def fetch_arxiv_ai_papers(limit: int = 10) -> list[dict]:
    print(f"📡 Fetching {limit} recent AI papers from arXiv...")

    for attempt in range(2):  # try twice
        try:
            if attempt > 0:
                print("⏳ Waiting 10 seconds before retrying arXiv...")
                await asyncio.sleep(10)

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(
                    "https://export.arxiv.org/api/query",
                    params={
                        "search_query": "cat:cs.AI OR cat:cs.LG OR cat:cs.CL",
                        "sortBy": "submittedDate",
                        "sortOrder": "descending",
                        "max_results": limit,
                    },
                )

                if response.status_code == 429:
                    print(f"⚠️ arXiv rate limited (attempt {attempt + 1}/2)")
                    continue

                if response.status_code != 200:
                    print(f"⚠️ arXiv returned status {response.status_code} — skipping")
                    return []

                if not response.text or len(response.text) < 100:
                    print("⚠️ arXiv returned empty response — skipping")
                    return []

                root = ET.fromstring(response.text)
                ns = {"atom": "http://www.w3.org/2005/Atom"}

                papers = []
                for entry in root.findall("atom:entry", ns):
                    title = entry.find("atom:title", ns)
                    summary = entry.find("atom:summary", ns)
                    link = entry.find("atom:id", ns)

                    if title is not None and summary is not None:
                        papers.append(
                            {
                                "title": title.text.strip(),
                                "url": link.text.strip() if link is not None else "",
                                "text": f"{title.text.strip()}. {summary.text.strip()}",
                                "source": "arxiv",
                            }
                        )

                print(f"✅ Fetched {len(papers)} arXiv papers")
                return papers

        except Exception as e:
            print(f"⚠️ arXiv fetch failed: {e} — skipping")
            return []

    print("⚠️ arXiv failed after 2 attempts — skipping")
    return []


# ── Step 2: Chunk text ────────────────────────────
def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


# ── Step 3: Embed text using OpenAI ───────────────
def embed_text(text: str) -> list[float]:
    response = openai_client.embeddings.create(
        input=text,
        model=EMBEDDING_MODEL,
    )
    return response.data[0].embedding


# ── Step 4: Store in Qdrant (no duplicates) ───────
def store_in_qdrant(chunks: list[str], metadata: dict) -> int:
    points = []
    for chunk in chunks:
        vector = embed_text(chunk)

        # Deterministic ID — same content = same ID = no duplicates
        chunk_id = generate_deterministic_id(chunk)

        point = PointStruct(
            id=chunk_id,
            vector=vector,
            payload={
                "text": chunk,
                "source": metadata.get("source"),
                "title": metadata.get("title"),
                "url": metadata.get("url"),
            },
        )
        points.append(point)

    # upsert = insert if new, overwrite if ID already exists
    qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
    )
    return len(points)


# ── Main pipeline ─────────────────────────────────
async def main():
    print("🚀 Starting knowledge base ingestion...")

    # Fetch sequentially to avoid rate limits
    hn_stories = await fetch_hn_ai_stories(limit=10)
    arxiv_papers = await fetch_arxiv_ai_papers(limit=10)

    all_content = hn_stories + arxiv_papers
    print(f"📚 Total items to process: {len(all_content)}")

    total_chunks = 0
    for item in all_content:
        if not item["text"] or len(item["text"]) < 50:
            continue

        chunks = chunk_text(item["text"])
        stored = store_in_qdrant(chunks, item)
        total_chunks += stored
        print(f"  📄 [{item['source']}] {item['title'][:55]}... → {stored} chunks")

    print(f"\n✅ Ingestion complete — {total_chunks} total chunks in Qdrant")
    print(f"🔍 Check dashboard: {QDRANT_URL}/dashboard")


if __name__ == "__main__":
    asyncio.run(main())
