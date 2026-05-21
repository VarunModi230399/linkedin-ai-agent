# TODO: implement src/agent/memory/vector_store.py
import os

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "knowledge_base"
VECTOR_SIZE = 1536  # OpenAI text-embedding-3-large dimension


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
