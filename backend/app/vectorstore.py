"""
Qdrant vector store wrapper: collection bootstrap, upsert, and semantic search.
"""
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.config import settings

_client: QdrantClient | None = None


def get_qdrant() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    return _client


def ensure_collection() -> None:
    """Create the knowledge-base collection if it doesn't already exist."""
    client = get_qdrant()
    existing = {c.name for c in client.get_collections().collections}
    if settings.QDRANT_COLLECTION_NAME in existing:
        return
    client.create_collection(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        vectors_config=qmodels.VectorParams(
            size=settings.EMBEDDING_DIMENSIONS,
            distance=qmodels.Distance.COSINE,
        ),
    )


def recreate_collection() -> None:
    """Drop and recreate the collection (used by full reindex)."""
    client = get_qdrant()
    client.recreate_collection(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        vectors_config=qmodels.VectorParams(
            size=settings.EMBEDDING_DIMENSIONS,
            distance=qmodels.Distance.COSINE,
        ),
    )


def upsert_chunks(
    document_id: str,
    filename: str,
    chunks: list[str],
    embeddings: list[list[float]],
) -> int:
    """Insert chunk vectors with metadata payload. Returns number of points written."""
    client = get_qdrant()
    points = [
        qmodels.PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "document_id": document_id,
                "filename": filename,
                "chunk_index": idx,
                "text": chunk,
            },
        )
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]
    if points:
        client.upsert(collection_name=settings.QDRANT_COLLECTION_NAME, points=points)
    return len(points)


def delete_by_document_id(document_id: str) -> None:
    client = get_qdrant()
    client.delete(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="document_id", match=qmodels.MatchValue(value=document_id)
                    )
                ]
            )
        ),
    )


def search(query_vector: list[float], top_k: int) -> list[dict[str, Any]]:
    """Semantic search. Returns list of {text, filename, document_id, score}."""
    client = get_qdrant()
    try:
        results = client.search(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
        )
    except Exception:
        # Collection may not exist yet (no documents indexed)
        return []

    return [
        {
            "text": r.payload.get("text", ""),
            "filename": r.payload.get("filename", ""),
            "document_id": r.payload.get("document_id", ""),
            "score": r.score,
        }
        for r in results
    ]
