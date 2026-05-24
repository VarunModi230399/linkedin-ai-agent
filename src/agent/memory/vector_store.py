# src/agent/memory/vector_store.py
#
# Qdrant vector store for the knowledge base.
# Handles collection creation, ingestion, and retrieval.
# Returns rich metadata with every search result.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
)
from src.agent.core.settings import (
    QDRANT_URL,
    OPENAI_API_KEY,
    OPENAI_EMBEDDING_MODEL,
)
from openai import OpenAI

# ── Config ────────────────────────────────────────
COLLECTION_NAME = "knowledge_base"
VECTOR_SIZE = 3072  # text-embedding-3-large


# ── Clients ───────────────────────────────────────
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


def get_openai_client() -> OpenAI:
    return OpenAI(api_key=OPENAI_API_KEY)


# ── Collection management ─────────────────────────
def create_collection_if_not_exists():
    client = get_qdrant_client()
    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )
        print(f"✅ Created collection: {COLLECTION_NAME}")
    else:
        print(f"✅ Collection exists: {COLLECTION_NAME}")

    return client


# ── Embedding ─────────────────────────────────────
def embed_query(text: str) -> list[float]:
    """
    Embeds a search query using OpenAI.
    Uses the same model as ingestion for consistency.
    """
    client = get_openai_client()
    response = client.embeddings.create(
        input=text,
        model=OPENAI_EMBEDDING_MODEL,
    )
    return response.data[0].embedding


# ── Search ────────────────────────────────────────
def search_knowledge_base(
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Searches Qdrant for the most relevant chunks.

    Returns rich metadata with every result including:
    - text: the chunk content
    - title: article/paper title
    - url: original source URL
    - author: author name if available
    - published_date: publication date if available
    - publication: source name (Dev.to, arXiv, etc.)
    - score: cosine similarity score (0-1)
    """
    client = get_qdrant_client()
    query_vector = embed_query(query)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    )

    formatted = []
    for result in results.points:
        payload = result.payload or {}
        formatted.append(
            {
                "text": payload.get("text", ""),
                "title": payload.get("title", ""),
                "url": payload.get("url", ""),
                "author": payload.get("author", ""),
                "published_date": payload.get("published_date", ""),
                "publication": payload.get("publication", ""),
                "source": payload.get("source", ""),
                "score": round(result.score, 4),
            }
        )

    return formatted
