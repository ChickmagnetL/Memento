"""
Qdrant vector database client for Memento.

Phase 1 scope: Initialize embedded Qdrant instance and ensure collection exists.
Indexing and search operations are added in Phase 3 (RAG implementation).

Note: `from qdrant_client import QdrantClient` resolves to the INSTALLED
qdrant-client package (absolute import), not this module. The local class is
named QdrantStore to avoid confusion.

Author: Memento Team
Last Updated: 2026-06-07
"""

from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)


class QdrantStore:
    """
    Embedded Qdrant client for vector storage.

    Phase 1: Initialize and create collection.
    Phase 3+: Add indexing, search, and deletion operations.

    Uses local on-disk persistence (no separate server process).

    Attributes:
        storage_path (Path): Directory where Qdrant persists data
        collection_name (str): Name of the vector collection
        _client (QdrantClient): Underlying qdrant-client instance
    """

    def __init__(self, storage_path: Path | str, collection_name: str = "documents"):
        """
        Initialize Qdrant store.

        Args:
            storage_path: Directory where Qdrant persists data
            collection_name: Name of the vector collection
        """
        self.storage_path = Path(storage_path)
        self.collection_name = collection_name
        self._client: QdrantClient | None = None

    def connect(self, vector_size: int = 768) -> None:
        """
        Initialize the embedded Qdrant client and ensure the collection exists.

        Args:
            vector_size: Dimension of stored vectors (depends on embedding model)
        """
        # Ensure storage directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Initialize embedded Qdrant client
        self._client = QdrantClient(path=str(self.storage_path))

        # Check if collection exists
        existing = {c.name for c in self._client.get_collections().collections}
        if self.collection_name not in existing:
            # Create collection with cosine distance
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    def close(self) -> None:
        """Close the embedded Qdrant client."""
        if self._client:
            self._client.close()
            self._client = None

    def _require_client(self) -> QdrantClient:
        """Return the connected client or raise a clear error."""
        if self._client is None:
            raise RuntimeError("QdrantStore is not connected")
        return self._client

    @staticmethod
    def _document_filter(document_id: str) -> Filter:
        return Filter(
            must=[
                FieldCondition(
                    key="document_id", match=MatchValue(value=document_id)
                )
            ]
        )

    def upsert_points(
        self,
        *,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None:
        """Upsert chunk points with metadata payloads."""
        client = self._require_client()
        if not ids:
            return
        if len(ids) != len(vectors) or len(ids) != len(payloads):
            raise ValueError("ids, vectors, and payloads must have the same length")
        client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(id=point_id, vector=vector, payload=payload)
                for point_id, vector, payload in zip(ids, vectors, payloads)
            ],
        )

    def delete_for_document(self, document_id: str) -> None:
        """Delete all points belonging to a document."""
        client = self._require_client()
        client.delete(
            collection_name=self.collection_name,
            points_selector=self._document_filter(document_id),
        )

    def count_for_document(self, document_id: str) -> int:
        """Count points belonging to a document."""
        client = self._require_client()
        result = client.count(
            collection_name=self.collection_name,
            count_filter=self._document_filter(document_id),
            exact=True,
        )
        return result.count

    def search_points(
        self, *, vector: list[float], top_k: int
    ) -> list[dict]:
        """Vector similarity search returning payloads with scores."""
        client = self._require_client()
        response = client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=top_k,
            with_payload=True,
        )
        return [
            {"score": point.score, "payload": dict(point.payload or {})}
            for point in response.points
        ]

    def scroll_all_points(self, *, batch_size: int = 256) -> list[dict]:
        """Return payloads of all points (used to build the BM25 corpus)."""
        client = self._require_client()
        payloads: list[dict] = []
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=self.collection_name,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            payloads.extend(dict(point.payload or {}) for point in points)
            if offset is None:
                break
        return payloads
