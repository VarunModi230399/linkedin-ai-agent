# TODO: implement src/agent/memory/vector_store.py
import os

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "knowledge_base"
VECTOR_SIZE = 3072  # OpenAI text-embedding-3-large dimension


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


def create_collection_if_not_exists():
    client = get_qdrant_client()

    # Check if collection already exists
    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,  # measures similarity between vectors
            ),
        )
        print(f"✅ Created collection: {COLLECTION_NAME}")
    else:
        print(f"✅ Collection already exists: {COLLECTION_NAME}")

    return client


# ── Retrieval ─────────────────────────────────────


def embed_query(text: str) -> list[float]:
    """Convert a search query into a vector using OpenAI."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
    from src.agent.core.settings import OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(
        input=text,
        model=OPENAI_EMBEDDING_MODEL,
    )
    return response.data[0].embedding


def search_knowledge_base(query: str, top_k: int = 5) -> list[dict]:
    """
    Search Qdrant for the most relevant chunks matching the query.
    Returns a list of results with text, title, url, and score.
    """
    client = get_qdrant_client()

    # Convert query to vector
    query_vector = embed_query(query)

    # Search Qdrant — using query_points (new API in v1.7+)
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    )

    # Format results cleanly
    formatted = []
    for result in results.points:
        formatted.append(
            {
                "text": result.payload.get("text", ""),
                "title": result.payload.get("title", ""),
                "url": result.payload.get("url", ""),
                "score": round(result.score, 4),
            }
        )

    return formatted
