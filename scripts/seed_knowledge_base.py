# scripts/seed_knowledge_base.py
import sys
from pathlib import Path

# Add project root to Python path so we can import src/
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import from central settings — loads correct .env automatically
from src.agent.core.settings import OPENAI_API_KEY, QDRANT_URL

import asyncio
import httpx
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import uuid

# ── Config ────────────────────────────────────────
COLLECTION_NAME = "knowledge_base"
EMBEDDING_MODEL = "text-embedding-3-large"

openai_client = OpenAI(api_key=OPENAI_API_KEY)
qdrant_client = QdrantClient(url=QDRANT_URL)


# ── Step 1: Fetch top AI stories from Hacker News ─
async def fetch_hn_ai_stories(limit: int = 10) -> list[dict]:
    print(f"📡 Fetching top {limit} AI stories from Hacker News...")
    async with httpx.AsyncClient() as client:
        # Get top story IDs
        response = await client.get(
            "https://hn.algolia.com/api/v1/search",
            params={
                "query": "artificial intelligence machine learning LLM",
                "tags": "story",
                "hitsPerPage": limit,
            },
        )
        data = response.json()
        stories = []
        for hit in data.get("hits", []):
            title = hit.get("title", "")
            url = hit.get("url", "")
            text = hit.get("story_text") or ""
            if title:
                stories.append(
                    {
                        "title": title,
                        "url": url,
                        "text": f"{title}. {text}".strip(),
                        "source": "hackernews",
                    }
                )
        print(f"✅ Fetched {len(stories)} stories")
        return stories


# ── Step 2: Chunk text into smaller pieces ────────
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


# ── Step 4: Store in Qdrant ───────────────────────
def store_in_qdrant(chunks: list[str], metadata: dict):
    points = []
    for chunk in chunks:
        vector = embed_text(chunk)
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "text": chunk,
                "source": metadata.get("source"),
                "title": metadata.get("title"),
                "url": metadata.get("url"),
            },
        )
        points.append(point)

    qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
    )
    return len(points)


# ── Main pipeline ─────────────────────────────────
async def main():
    print("🚀 Starting knowledge base ingestion...")
    stories = await fetch_hn_ai_stories(limit=10)

    total_chunks = 0
    for story in stories:
        if not story["text"] or len(story["text"]) < 50:
            continue

        chunks = chunk_text(story["text"])
        stored = store_in_qdrant(chunks, story)
        total_chunks += stored
        print(f"  📄 {story['title'][:60]}... → {stored} chunks stored")

    print(f"\n✅ Ingestion complete — {total_chunks} total chunks in Qdrant")
    print(f"🔍 Check dashboard: {QDRANT_URL}/dashboard")


if __name__ == "__main__":
    asyncio.run(main())
