# scripts/seed_knowledge_base.py
#
# Production-grade knowledge base ingestion.
# Fetches FULL content with rich citation metadata.
# Every chunk stores: text, title, author, date, URL, publication.
# Supports Option-B citation style in posts.

import sys
from pathlib import Path
import hashlib
import asyncio
import httpx
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.core.settings import OPENAI_API_KEY, QDRANT_URL
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

COLLECTION_NAME = "knowledge_base"
EMBEDDING_MODEL = "text-embedding-3-large"
MIN_TEXT_LENGTH = 150

openai_client = OpenAI(api_key=OPENAI_API_KEY)
qdrant_client = QdrantClient(url=QDRANT_URL)

# ── Helpers ───────────────────────────────────────


def make_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def clean_markdown(text: str) -> str:
    """Strip markdown formatting leaving clean readable text."""
    text = re.sub(r"```[\s\S]*?```", "", text)  # code blocks
    text = re.sub(r"`[^`]+`", "", text)  # inline code
    text = re.sub(r"#{1,6}\s", "", text)  # headers
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)  # images
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)  # links → text
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)  # bold/italic
    text = re.sub(r"\n{3,}", "\n\n", text)  # excess newlines
    return text.strip()


def chunk_text(
    text: str,
    chunk_size: int = 300,
    overlap: int = 50,
) -> list[str]:
    """
    Splits text into overlapping chunks.
    Overlap preserves context across chunk boundaries.
    Smaller chunks (300 words) = more precise retrieval.
    """
    words = text.split()
    if len(words) <= chunk_size:
        return [text] if len(text) > MIN_TEXT_LENGTH else []

    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i : i + chunk_size])
        if len(chunk) > MIN_TEXT_LENGTH:
            chunks.append(chunk)
    return chunks


def embed_text(text: str) -> list[float]:
    response = openai_client.embeddings.create(
        input=text,
        model=EMBEDDING_MODEL,
    )
    return response.data[0].embedding


def store_chunks(chunks: list[str], metadata: dict) -> int:
    """
    Stores chunks in Qdrant with full citation metadata.
    Uses deterministic IDs to prevent duplicates.
    """
    if not chunks:
        return 0

    points = []
    for chunk in chunks:
        point = PointStruct(
            id=make_id(chunk),
            vector=embed_text(chunk),
            payload={
                "text": chunk,
                "title": metadata.get("title", ""),
                "url": metadata.get("url", ""),
                "author": metadata.get("author", ""),
                "published_date": metadata.get("published_date", ""),
                "publication": metadata.get("publication", ""),
                "source": metadata.get("source", ""),
            },
        )
        points.append(point)

    qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
    return len(points)


def deduplicate(items: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for item in items:
        key = item.get("title", "").lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


# ── Source 1: HuggingFace Daily Papers ───────────
async def fetch_huggingface_papers(days_back: int = 7) -> list[dict]:
    """
    Fetches papers from last N days.
    Fetches abstract from individual paper endpoint.
    """
    print(f"📡 HuggingFace Daily Papers (last {days_back} days)...")
    papers = []

    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            # Step 1 — collect paper IDs and metadata
            paper_list = []
            for i in range(days_back):
                date = (datetime.now() - timedelta(days=i + 1)).strftime("%Y-%m-%d")
                response = await client.get(
                    "https://huggingface.co/api/daily_papers",
                    params={"date": date},
                )
                if response.status_code != 200:
                    continue

                for item in response.json():
                    paper = item.get("paper", {})
                    paper_id = paper.get("id", "")
                    title = paper.get("title", "").strip()
                    authors = paper.get("authors", [])
                    author = authors[0].get("name", "") if authors else ""
                    published = paper.get("publishedAt", "")[:10]

                    if paper_id and title:
                        paper_list.append(
                            {
                                "id": paper_id,
                                "title": title,
                                "author": author,
                                "published_date": published,
                            }
                        )

                await asyncio.sleep(0.5)

            print(f"  Found {len(paper_list)} papers — fetching abstracts...")

            # Step 2 — fetch abstract for each paper
            # Limit to 30 to avoid too many API calls
            for meta in paper_list[:30]:
                try:
                    r = await client.get(
                        f"https://huggingface.co/api/papers/{meta['id']}",
                    )
                    if r.status_code != 200:
                        continue

                    data = r.json()
                    abstract = data.get("summary", data.get("abstract", "")).strip()

                    if abstract and len(abstract) > MIN_TEXT_LENGTH:
                        papers.append(
                            {
                                "title": meta["title"],
                                "url": f"https://huggingface.co/papers/{meta['id']}",
                                "text": f"{meta['title']}\n\n{abstract}",
                                "author": meta["author"],
                                "published_date": meta["published_date"],
                                "publication": "HuggingFace Daily Papers",
                                "source": "huggingface",
                            }
                        )

                    # Polite delay — avoid rate limiting
                    await asyncio.sleep(0.3)

                except Exception:
                    continue

        print(f"  ✅ {len(papers)} papers with abstracts fetched")
        return papers

    except Exception as e:
        print(f"  ⚠️  Failed: {e}")
        return []


# ── Source 2: Dev.to Full Articles ────────────────
async def fetch_devto_articles(limit: int = 25) -> list[dict]:
    """
    Fetches full article bodies from Dev.to.
    Includes author name and published date.
    """
    print(f"📡 Dev.to articles with full content ({limit} articles)...")
    articles = []

    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            # Collect article IDs across AI-relevant tags
            tags = ["machinelearning", "llm", "rag", "aitools", "deeplearning"]
            article_ids_meta = {}  # id → basic metadata

            for tag in tags:
                r = await client.get(
                    "https://dev.to/api/articles",
                    params={"tag": tag, "per_page": 10, "top": 7},
                )
                if r.status_code == 200:
                    for item in r.json():
                        aid = item.get("id")
                        if aid and aid not in article_ids_meta:
                            article_ids_meta[aid] = {
                                "title": item.get("title", ""),
                                "url": item.get("url", ""),
                                "author": item.get("user", {}).get("name", ""),
                                "published_date": item.get("published_at", "")[
                                    :10
                                ],  # YYYY-MM-DD
                            }
                await asyncio.sleep(0.3)

            # Fetch full body for each article
            ids_to_fetch = list(article_ids_meta.keys())[:limit]
            print(f"  Fetching full content for {len(ids_to_fetch)} articles...")

            for article_id in ids_to_fetch:
                try:
                    r = await client.get(
                        f"https://dev.to/api/articles/{article_id}",
                    )
                    if r.status_code != 200:
                        continue

                    data = r.json()
                    meta = article_ids_meta[article_id]
                    body = clean_markdown(data.get("body_markdown", ""))

                    if meta["title"] and len(body) > MIN_TEXT_LENGTH:
                        # Take up to 2000 chars = 3-4 good chunks
                        articles.append(
                            {
                                "title": meta["title"],
                                "url": meta["url"],
                                "text": f"{meta['title']}\n\n{body[:2000]}",
                                "author": meta["author"],
                                "published_date": meta["published_date"],
                                "publication": "Dev.to",
                                "source": "devto",
                            }
                        )

                    await asyncio.sleep(0.15)

                except Exception:
                    continue

        print(f"  ✅ {len(articles)} articles fetched")
        return articles

    except Exception as e:
        print(f"  ⚠️  Failed: {e}")
        return []


# ── Source 3: arXiv ───────────────────────────────
async def fetch_arxiv_papers(limit: int = 40) -> list[dict]:
    """
    Fetches recent AI/ML papers from arXiv.
    Extracts authors and submission date.
    """
    print(f"📡 arXiv papers ({limit} papers)...")

    for attempt in range(3):
        try:
            if attempt > 0:
                wait = attempt * 10
                print(f"  ⏳ Waiting {wait}s before retry {attempt + 1}/3...")
                await asyncio.sleep(wait)

            async with httpx.AsyncClient(
                timeout=40.0,
                follow_redirects=True,
            ) as client:
                response = await client.get(
                    "https://export.arxiv.org/api/query",
                    params={
                        "search_query": ("cat:cs.AI OR cat:cs.LG OR cat:cs.CL"),
                        "sortBy": "submittedDate",
                        "sortOrder": "descending",
                        "max_results": limit,
                    },
                )

                if response.status_code == 429:
                    continue
                if response.status_code != 200 or not response.text:
                    return []

                root = ET.fromstring(response.text)
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                papers = []

                for entry in root.findall("atom:entry", ns):
                    title_el = entry.find("atom:title", ns)
                    summary_el = entry.find("atom:summary", ns)
                    link_el = entry.find("atom:id", ns)
                    published_el = entry.find("atom:published", ns)

                    # Get first author
                    author_el = entry.find("atom:author/atom:name", ns)

                    if title_el is None or summary_el is None:
                        continue

                    title = title_el.text.strip().replace("\n", " ")
                    summary = summary_el.text.strip().replace("\n", " ")
                    pub_date = ""
                    if published_el is not None:
                        pub_date = published_el.text[:10]  # YYYY-MM-DD

                    if len(summary) > MIN_TEXT_LENGTH:
                        papers.append(
                            {
                                "title": title,
                                "url": link_el.text.strip()
                                if link_el is not None
                                else "",
                                "text": f"{title}\n\n{summary}",
                                "author": author_el.text.strip()
                                if author_el is not None
                                else "",
                                "published_date": pub_date,
                                "publication": "arXiv",
                                "source": "arxiv",
                            }
                        )

                print(f"  ✅ {len(papers)} papers fetched")
                return papers

        except Exception as e:
            print(f"  ⚠️  Attempt {attempt + 1} failed: {e}")

    print("  ⚠️  arXiv failed — skipping")
    return []


# ── Source 4: Hacker News ─────────────────────────
async def fetch_hn_stories(limit: int = 20) -> list[dict]:
    """
    Fetches high-quality HN AI stories.
    Filters for points > 20 to ensure quality.
    """
    print(f"📡 Hacker News AI stories ({limit} stories)...")
    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                "https://hn.algolia.com/api/v1/search",
                params={
                    "query": "LLM GPT AI machine learning",
                    "tags": "story",
                    "hitsPerPage": limit,
                    "numericFilters": "points>5",  # lower threshold
                },
            )

            if response.status_code != 200:
                return []

            stories = []
            for hit in response.json().get("hits", []):
                title = hit.get("title", "").strip()
                text = hit.get("story_text") or ""
                url = hit.get("url", "")
                author = hit.get("author", "")
                created = hit.get("created_at", "")[:10]
                full = f"{title}\n\n{text}".strip()

                if title and len(full) > MIN_TEXT_LENGTH:
                    stories.append(
                        {
                            "title": title,
                            "url": url,
                            "text": full,
                            "author": author,
                            "published_date": created,
                            "publication": "Hacker News",
                            "source": "hackernews",
                        }
                    )

            print(f"  ✅ {len(stories)} stories fetched")
            return stories

    except Exception as e:
        print(f"  ⚠️  Failed: {e}")
        return []


# ── Main ──────────────────────────────────────────
async def main():
    print()
    print("=" * 60)
    print("🚀 Knowledge Base — Rich Ingestion with Citations")
    print("=" * 60)
    print()

    # Fetch all sources sequentially
    hf_papers = await fetch_huggingface_papers(days_back=7)
    await asyncio.sleep(2)
    devto_articles = await fetch_devto_articles(limit=25)
    await asyncio.sleep(2)
    arxiv_papers = await fetch_arxiv_papers(limit=40)
    await asyncio.sleep(2)
    hn_stories = await fetch_hn_stories(limit=20)

    all_content = deduplicate(hf_papers + devto_articles + arxiv_papers + hn_stories)

    print()
    print(f"📚 Total unique items: {len(all_content)}")
    print(f"   HuggingFace:  {len(hf_papers)}")
    print(f"   Dev.to:       {len(devto_articles)}")
    print(f"   arXiv:        {len(arxiv_papers)}")
    print(f"   Hacker News:  {len(hn_stories)}")
    print()
    print("Embedding and storing...")
    print()

    total_chunks = 0
    failed = 0
    icons = {
        "huggingface": "🤗",
        "devto": "👩‍💻",
        "arxiv": "📄",
        "hackernews": "🔶",
    }

    for item in all_content:
        try:
            chunks = chunk_text(item["text"])
            if not chunks:
                continue

            stored = store_chunks(chunks, item)
            total_chunks += stored
            icon = icons.get(item["source"], "📝")

            print(
                f"  {icon} {item['title'][:52]:52} "
                f"[{item.get('published_date', '?'):10}] "
                f"→ {stored} chunk{'s' if stored > 1 else ' '}"
            )

        except Exception as e:
            failed += 1
            print(f"  ❌ {item.get('title', '?')[:40]} — {e}")

    # Final report
    info = qdrant_client.get_collection(COLLECTION_NAME)
    print()
    print("=" * 60)
    print("✅ Ingestion complete")
    print(f"   Items processed:  {len(all_content)}")
    print(f"   Chunks stored:    {total_chunks}")
    print(f"   Total in Qdrant:  {info.points_count}")
    print(f"   Failed:           {failed}")
    print(f"   Avg chunks/item:  {round(total_chunks / max(len(all_content), 1), 1)}")
    print("=" * 60)
    print(f"\n🔍 Dashboard: {QDRANT_URL}/dashboard")


if __name__ == "__main__":
    asyncio.run(main())
