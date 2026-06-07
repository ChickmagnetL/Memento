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
from qdrant_client.models import Distance, VectorParams


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
