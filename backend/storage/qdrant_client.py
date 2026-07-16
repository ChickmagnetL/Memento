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

import uuid
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

    SUMMARY_COLLECTION = "document_summaries"

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

        self._ensure_collection(self.collection_name, vector_size)

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

    def _resolve_collection_name(self, name: str | None) -> str:
        return self.collection_name if name is None else name

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

    def _ensure_collection(self, name: str, vector_size: int) -> None:
        client = self._require_client()
        existing = {c.name for c in client.get_collections().collections}
        if name not in existing:
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    def collection_vector_size(self, name: str | None = None) -> int | None:
        """Return the dense vector size for a collection, or None if missing."""
        client = self._require_client()
        collection_name = self._resolve_collection_name(name)
        existing = {c.name for c in client.get_collections().collections}
        if collection_name not in existing:
            return None
        info = client.get_collection(collection_name)
        return info.config.params.vectors.size

    def recreate_collection(
        self, name: str | None = None, *, vector_size: int
    ) -> None:
        """Replace a collection with a fresh cosine collection of the given size."""
        client = self._require_client()
        collection_name = self._resolve_collection_name(name)
        # qdrant-client 1.11 leaves the local collection's SQLite handle open.
        # Windows then cannot remove its directory and the recreated collection
        # silently reloads the old points from disk.
        local_client = getattr(client, "_client", None)
        local_collections = getattr(local_client, "collections", None)
        if isinstance(local_collections, dict):
            local_collection = local_collections.get(collection_name)
            if local_collection is not None:
                local_collection.close()
        client.delete_collection(collection_name=collection_name)
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    def ensure_summary_collection(self, vector_size: int) -> None:
        """Create the document summary collection if it does not exist."""
        self._ensure_collection(self.SUMMARY_COLLECTION, vector_size)

    def recreate_summary_collection(self, *, vector_size: int) -> None:
        """Replace the document summary collection with a fresh one."""
        self.recreate_collection(self.SUMMARY_COLLECTION, vector_size=vector_size)

    @staticmethod
    def _document_point_id(document_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_OID, document_id))

    def upsert_summary(
        self,
        *,
        document_id: str,
        vector: list[float],
        title: str,
        brief: str,
    ) -> None:
        """Insert or update a single document summary point."""
        client = self._require_client()
        point_id = self._document_point_id(document_id)
        client.upsert(
            collection_name=self.SUMMARY_COLLECTION,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={"document_id": document_id, "title": title, "brief": brief},
                )
            ],
        )

    def search_summaries(
        self, *, vector: list[float], top_k: int
    ) -> list[dict]:
        """Search document summaries by vector similarity."""
        client = self._require_client()
        response = client.query_points(
            collection_name=self.SUMMARY_COLLECTION,
            query=vector,
            limit=top_k,
            with_payload=True,
        )
        return [
            {"score": point.score, "payload": dict(point.payload or {})}
            for point in response.points
        ]

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
