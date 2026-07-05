"""Embedding preset dimension preview and background reindex job management."""

import asyncio
import copy
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from config.settings import get_settings
from core.rag.embedding import EmbeddingError
from core.rag.document_summary_store import DocumentSummaryStore
from core.rag.indexer import DocumentIndexer

PROBE_TEXT = "memento embedding dimension probe"


class EmbeddingReindexJobManager:
    """Single-job manager for embedding index rebuilds."""

    def __init__(self, *, sqlite, qdrant) -> None:
        self.sqlite = sqlite
        self.qdrant = qdrant
        self._jobs: dict[str, dict[str, Any]] = {}
        self._running_job_id: str | None = None

    async def preview_switch(self, *, preset_id: str, embedding_client) -> dict:
        """Probe target dimension and compare with the current Qdrant dimension."""
        vectors = await asyncio.to_thread(embedding_client.embed, [PROBE_TEXT])
        if not vectors or not vectors[0]:
            raise EmbeddingError("Embedding probe returned an empty vector")

        new_dimension = len(vectors[0])
        current_dimension = self.qdrant.collection_vector_size()
        if current_dimension is None:
            current_dimension = new_dimension

        documents = await self.sqlite.list_documents()
        indexed_count = sum(
            1 for document in documents if document.get("status") == "indexed"
        )
        return {
            "preset_id": preset_id,
            "current_dimension": current_dimension,
            "new_dimension": new_dimension,
            "same_dimension": current_dimension == new_dimension,
            "indexed_document_count": indexed_count,
        }

    def get_job(self, job_id: str) -> dict | None:
        """Return a job snapshot by id."""
        job = self._jobs.get(job_id)
        if job is None:
            return None
        return self._snapshot_job(job)

    def active_job(self) -> dict | None:
        """Return the running job snapshot, if any."""
        if self._running_job_id is None:
            return None
        return self.get_job(self._running_job_id)

    def start_job(
        self,
        *,
        preset_id: str,
        embedding_client_factory: Callable[[], object],
        activate_preset: Callable[[str], None],
        runner: Callable[[dict], Awaitable[None]] | None = None,
    ) -> dict:
        """Create and schedule one background rebuild job."""
        if self._running_job_id is not None:
            raise RuntimeError("Embedding index rebuild is already running")

        job_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        job = {
            "id": job_id,
            "preset_id": preset_id,
            "status": "pending",
            "stage": "queued",
            "total_documents": 0,
            "processed_documents": 0,
            "failed_documents": [],
            "error": None,
            "started_at": now,
            "finished_at": None,
        }
        self._jobs[job_id] = job
        self._running_job_id = job_id

        async def run() -> None:
            try:
                job["status"] = "running"
                job["stage"] = "probing"
                if runner is None:
                    await self._run_reindex_job(
                        job,
                        embedding_client_factory=embedding_client_factory,
                        activate_preset=activate_preset,
                    )
                else:
                    await runner(job)
                if job["status"] == "running":
                    job["status"] = "completed"
                    job["stage"] = "completed"
            except Exception as exc:
                job["status"] = "failed"
                job["stage"] = "failed"
                job["error"] = str(exc) or type(exc).__name__
            finally:
                job["finished_at"] = datetime.now(timezone.utc).isoformat()
                self._running_job_id = None

        coroutine = run()
        try:
            task = asyncio.create_task(coroutine)
        except Exception:
            coroutine.close()
            self._jobs.pop(job_id, None)
            self._running_job_id = None
            raise
        return {"job": self._snapshot_job(job), "task": task}

    async def _run_reindex_job(
        self,
        job: dict,
        *,
        embedding_client_factory: Callable[[], object],
        activate_preset: Callable[[str], None],
    ) -> None:
        embedding_client = embedding_client_factory()
        vectors = await asyncio.to_thread(embedding_client.embed, [PROBE_TEXT])
        if not vectors or not vectors[0]:
            raise EmbeddingError("Embedding probe returned an empty vector")

        new_dimension = len(vectors[0])
        indexed_documents = [
            document
            for document in await self.sqlite.list_documents()
            if document.get("status") == "indexed"
        ]
        job["total_documents"] = len(indexed_documents)

        job["stage"] = "activating_preset"
        activate_preset(job["preset_id"])

        job["stage"] = "recreating_collections"
        self.qdrant.recreate_collection(vector_size=new_dimension)
        self.qdrant.recreate_summary_collection(vector_size=new_dimension)

        settings = get_settings()
        indexer = DocumentIndexer(
            sqlite=self.sqlite,
            qdrant=self.qdrant,
            embedding_client=embedding_client,
            chunk_size=settings.rag.chunk_size,
            overlap=settings.rag.overlap,
        )
        summary_store = DocumentSummaryStore(
            sqlite=self.sqlite,
            qdrant=self.qdrant,
            embedding=embedding_client,
        )

        job["stage"] = "reindexing_documents"
        for document in indexed_documents:
            try:
                updated_document = await indexer.index(document)
                brief = updated_document.get("brief")
                if brief:
                    title = await summary_store._resolve_title(updated_document)
                    summary_vector = (await asyncio.to_thread(embedding_client.embed, [brief]))[
                        0
                    ]
                    await summary_store.save_summary(
                        document_id=updated_document["id"],
                        title=title,
                        l2=updated_document.get("summary"),
                        l3=brief,
                        l3_vector=summary_vector,
                    )
            except Exception as exc:
                self.qdrant.delete_for_document(document["id"])
                await self.sqlite.reset_document_indexing(document["id"])
                job["failed_documents"].append(
                    {
                        "document_id": document["id"],
                        "title": document.get("title"),
                        "error": str(exc) or type(exc).__name__,
                    }
                )
            finally:
                job["processed_documents"] += 1

        if job["failed_documents"]:
            job["status"] = "completed_with_errors"
            job["stage"] = "completed_with_errors"
        else:
            job["status"] = "completed"
            job["stage"] = "completed"

    def _snapshot_job(self, job: dict[str, Any]) -> dict[str, Any]:
        return copy.deepcopy(job)
