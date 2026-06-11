"""Document indexing orchestrator: file -> chunks -> embeddings -> Qdrant."""

import asyncio
import uuid
from pathlib import Path

from core.rag.chunking import chunk_markdown

# Arbitrary namespace UUID for generating deterministic point IDs.
_POINT_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _make_point_id(document_id: str, chunk_index: int) -> str:
    """Deterministic point ID so re-indexing overwrites, not duplicates."""
    return str(uuid.uuid5(_POINT_NAMESPACE, f"{document_id}:{chunk_index}"))


class DocumentIndexer:
    def __init__(
        self,
        *,
        sqlite,
        qdrant,
        embedding_client,
        chunk_size: int,
        overlap: int,
    ) -> None:
        self.sqlite = sqlite
        self.qdrant = qdrant
        self.embedding_client = embedding_client
        self.chunk_size = chunk_size
        self.overlap = overlap

    async def index(self, document: dict) -> dict:
        """Index one document and return the updated document record."""
        content = await asyncio.to_thread(
            Path(document["file_path"]).read_text, encoding="utf-8"
        )
        chunks = chunk_markdown(
            content,
            video_id=document["video_id"],
            document_id=document["id"],
            chunk_size=self.chunk_size,
            overlap=self.overlap,
        )
        if not chunks:
            raise ValueError("document produced no chunks")

        vectors = await asyncio.to_thread(
            self.embedding_client.embed, [chunk.text for chunk in chunks]
        )

        # Delete old points first so orphaned chunks from prior runs are
        # cleaned up; deterministic IDs prevent duplicates on re-upsert.
        self.qdrant.delete_for_document(document["id"])
        self.qdrant.upsert_points(
            ids=[_make_point_id(document["id"], c.chunk_index) for c in chunks],
            vectors=vectors,
            payloads=[
                {
                    "video_id": chunk.video_id,
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "title_path": chunk.title_path,
                    "text": chunk.text,
                    "start_timestamp": chunk.start_timestamp,
                }
                for chunk in chunks
            ],
        )

        updated = await self.sqlite.mark_document_indexed(
            document["id"], chunk_count=len(chunks)
        )
        if updated is None:
            raise RuntimeError("Indexed document could not be reloaded")
        return updated