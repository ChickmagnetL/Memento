"""Offline batched document indexer for large docs that timeout via HTTP /index."""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "backend"))
import bench_env  # noqa: F401

from config.settings import get_settings  # noqa: E402
from core.rag.chunking import chunk_markdown  # noqa: E402
from core.rag.embedding import EmbeddingError  # noqa: E402
from core.rag.embedding_supervisor import ensure_embedding_running  # noqa: E402
from storage.qdrant_client import QdrantStore  # noqa: E402
from storage.sqlite_client import SQLiteClient  # noqa: E402

_POINT_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

DEFAULT_DOCUMENT_ID = "d903d515ad124b8999552c522aee0cd7"


def _make_point_id(document_id: str, chunk_index: int) -> str:
    return str(uuid.uuid5(_POINT_NAMESPACE, f"{document_id}:{chunk_index}"))


class BatchedEmbeddingClient:
    def __init__(
        self,
        *,
        endpoint: str | None,
        api_key: str | None,
        model: str | None,
        batch_size: int = 12,
        timeout: float = 300.0,
    ) -> None:
        if not endpoint or not api_key or not model:
            raise EmbeddingError(
                "Embedding model is not configured "
                "(models.embedding endpoint/api_key/model required)"
            )
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.batch_size = batch_size
        self.timeout = timeout
        self._ensured = False

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self._ensured:
            ensure_embedding_running(self.endpoint)
            self._ensured = True
        all_vectors: list[list[float]] = []
        n = len(texts)
        total_batches = (n + self.batch_size - 1) // self.batch_size
        for bi, start in enumerate(range(0, n, self.batch_size), start=1):
            batch = texts[start : start + self.batch_size]
            print(f"  embedding batch {bi}/{total_batches} (size={len(batch)})")
            response = httpx.post(
                f"{self.endpoint}/embeddings",
                json={"model": self.model, "input": batch},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
            if response.status_code >= 400:
                raise RuntimeError(
                    f"HTTP {response.status_code}: {response.text[:200]}"
                )
            data = response.json().get("data")
            if not isinstance(data, list):
                raise RuntimeError("Malformed embedding API response")
            vectors: list[list[float] | None] = [None] * len(batch)
            for item in data:
                vectors[item["index"]] = item["embedding"]
            if any(v is None for v in vectors):
                raise RuntimeError("Malformed embedding API response")
            all_vectors.extend(vectors)  # type: ignore[arg-type]
        return all_vectors


async def index_document_batched(
    document_id: str,
    *,
    batch_size: int = 12,
    embed_timeout: float = 300.0,
) -> dict:
    settings = get_settings()
    data_dir = Path(settings.storage.data_dir).expanduser()
    sqlite = SQLiteClient(data_dir / "metadata.db")
    qdrant = QdrantStore(data_dir / "qdrant", collection_name="documents")
    await sqlite.connect()
    qdrant.connect(vector_size=settings.rag.vector_size)

    try:
        document = await sqlite.get_document(document_id)
        if document is None:
            raise ValueError(f"document not found: {document_id}")

        video = (
            await sqlite.get_video(document["video_id"])
            if document["video_id"]
            else None
        )
        platform = video["platform"] if video else None

        file_path = Path(document["file_path"])
        print(f"indexing document_id={document_id} file={file_path}")
        content = file_path.read_text(encoding="utf-8")
        chunks = chunk_markdown(
            content,
            video_id=document["video_id"],
            document_id=document["id"],
            chunk_size=settings.rag.chunk_size,
            overlap=settings.rag.overlap,
        )
        if not chunks:
            raise ValueError("document produced no chunks")

        print(f"  chunk_count={len(chunks)}")
        emb = BatchedEmbeddingClient(
            endpoint=settings.models.embedding.endpoint,
            api_key=settings.models.embedding.api_key,
            model=settings.models.embedding.model,
            batch_size=batch_size,
            timeout=embed_timeout,
        )
        vectors = emb.embed([chunk.text for chunk in chunks])

        qdrant.delete_for_document(document["id"])
        qdrant.upsert_points(
            ids=[_make_point_id(document["id"], c.chunk_index) for c in chunks],
            vectors=vectors,
            payloads=[
                {
                    "video_id": chunk.video_id,
                    "platform": platform,
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "title_path": chunk.title_path,
                    "text": chunk.text,
                    "start_timestamp": chunk.start_timestamp,
                }
                for chunk in chunks
            ],
        )

        updated = await sqlite.mark_document_indexed(
            document["id"], chunk_count=len(chunks)
        )
        if updated is None:
            raise RuntimeError("Indexed document could not be reloaded")
        print(
            f"  done document_id={updated.get('id')} "
            f"status={updated.get('status')} chunk_count={updated.get('chunk_count')}"
        )
        return updated
    finally:
        await sqlite.close()
        qdrant.close()


def index_document_batched_sync(document_id: str, **kwargs) -> dict:
    return asyncio.run(index_document_batched(document_id, **kwargs))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline batched index for large documents"
    )
    parser.add_argument(
        "document_id",
        nargs="?",
        default=DEFAULT_DOCUMENT_ID,
        help=f"document id (default: {DEFAULT_DOCUMENT_ID})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=12,
        help="embedding batch size (default: 12)",
    )
    parser.add_argument(
        "--embed-timeout",
        type=float,
        default=300.0,
        help="per-batch embedding HTTP timeout seconds (default: 300)",
    )
    args = parser.parse_args()
    result = index_document_batched_sync(
        args.document_id,
        batch_size=args.batch_size,
        embed_timeout=args.embed_timeout,
    )
    print(
        f"result: id={result.get('id')} status={result.get('status')} "
        f"chunk_count={result.get('chunk_count')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
