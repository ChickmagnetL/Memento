"""Tests for embedding dimension switch preview and background reindex jobs."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.rag.embedding_reindex as embedding_reindex_module
from core.rag.embedding import EmbeddingError
from core.rag.embedding_reindex import (
    PROBE_TEXT,
    EmbeddingReindexJobManager,
)
from storage.qdrant_client import QdrantStore
from storage.sqlite_client import SQLiteClient


class FakeEmbeddingClient:
    def __init__(self, dimension: int = 4, fail: bool = False):
        self.dimension = dimension
        self.fail = fail
        self.seen_texts: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.fail:
            raise EmbeddingError("embedding service unavailable")
        self.seen_texts.append(texts)
        return [[0.1] * self.dimension for _ in texts]


def _fake_settings(*, chunk_size: int = 800, overlap: int = 80):
    return SimpleNamespace(rag=SimpleNamespace(chunk_size=chunk_size, overlap=overlap))


async def _create_document(
    sqlite: SQLiteClient,
    tmp_path: Path,
    *,
    document_id: str,
    body: str,
    status: str = "indexed",
    title: str | None = None,
    video_id: str | None = None,
) -> dict:
    path = tmp_path / f"{document_id}.md"
    path.write_text(body, encoding="utf-8")
    return await sqlite.create_document(
        document_id=document_id,
        video_id=video_id,
        file_path=str(path),
        status=status,
        title=title,
    )


@pytest.fixture
async def sqlite(tmp_path: Path):
    client = SQLiteClient(tmp_path / "metadata.db")
    await client.connect()
    try:
        yield client
    finally:
        await client.close()


@pytest.fixture
def qdrant(tmp_path: Path):
    store = QdrantStore(tmp_path / "qdrant")
    store.connect(vector_size=4)
    store.ensure_summary_collection(vector_size=4)
    try:
        yield store
    finally:
        store.close()


@pytest.mark.asyncio
async def test_preview_reports_same_dimension(
    sqlite: SQLiteClient, qdrant: QdrantStore
):
    embedding_client = FakeEmbeddingClient(dimension=4)
    manager = EmbeddingReindexJobManager(sqlite=sqlite, qdrant=qdrant)

    preview = await manager.preview_switch(
        preset_id="embedding_new",
        embedding_client=embedding_client,
    )

    assert preview["preset_id"] == "embedding_new"
    assert preview["current_dimension"] == 4
    assert preview["new_dimension"] == 4
    assert preview["same_dimension"] is True
    assert preview["indexed_document_count"] == 0
    assert embedding_client.seen_texts == [[PROBE_TEXT]]


@pytest.mark.asyncio
async def test_preview_uses_new_dimension_when_qdrant_dimension_missing(
    sqlite: SQLiteClient, qdrant: QdrantStore
):
    qdrant.recreate_collection(vector_size=8)
    qdrant._client.delete_collection(collection_name=qdrant.collection_name)
    manager = EmbeddingReindexJobManager(sqlite=sqlite, qdrant=qdrant)

    preview = await manager.preview_switch(
        preset_id="embedding_new",
        embedding_client=FakeEmbeddingClient(dimension=6),
    )

    assert preview["current_dimension"] == 6
    assert preview["new_dimension"] == 6
    assert preview["same_dimension"] is True


@pytest.mark.asyncio
async def test_preview_reports_dimension_change_and_indexed_count(
    sqlite: SQLiteClient, qdrant: QdrantStore, tmp_path: Path
):
    path = tmp_path / "doc.md"
    path.write_text("# Doc\n\nbody", encoding="utf-8")
    await sqlite.create_document(document_id="d1", file_path=str(path), status="indexed")
    await sqlite.create_document(document_id="d2", file_path=str(path), status="raw")
    manager = EmbeddingReindexJobManager(sqlite=sqlite, qdrant=qdrant)

    preview = await manager.preview_switch(
        preset_id="embedding_new",
        embedding_client=FakeEmbeddingClient(dimension=8),
    )

    assert preview["current_dimension"] == 4
    assert preview["new_dimension"] == 8
    assert preview["same_dimension"] is False
    assert preview["indexed_document_count"] == 1


@pytest.mark.asyncio
async def test_preview_propagates_embedding_error(
    sqlite: SQLiteClient, qdrant: QdrantStore
):
    manager = EmbeddingReindexJobManager(sqlite=sqlite, qdrant=qdrant)

    with pytest.raises(EmbeddingError, match="embedding service unavailable"):
        await manager.preview_switch(
            preset_id="embedding_bad",
            embedding_client=FakeEmbeddingClient(fail=True),
        )


@pytest.mark.asyncio
async def test_start_rejects_second_running_job(
    sqlite: SQLiteClient, qdrant: QdrantStore
):
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_runner(job):
        started.set()
        await release.wait()

    manager = EmbeddingReindexJobManager(sqlite=sqlite, qdrant=qdrant)
    first = manager.start_job(
        preset_id="embedding_a",
        embedding_client_factory=lambda: FakeEmbeddingClient(dimension=8),
        activate_preset=lambda preset_id: None,
        runner=slow_runner,
    )
    await started.wait()

    with pytest.raises(RuntimeError, match="Embedding index rebuild is already running"):
        manager.start_job(
            preset_id="embedding_b",
            embedding_client_factory=lambda: FakeEmbeddingClient(dimension=8),
            activate_preset=lambda preset_id: None,
            runner=slow_runner,
        )

    release.set()
    await first["task"]


@pytest.mark.asyncio
async def test_start_job_creates_snapshot_and_schedules_background_task(
    sqlite: SQLiteClient, qdrant: QdrantStore
):
    release = asyncio.Event()

    async def slow_runner(job):
        await release.wait()

    manager = EmbeddingReindexJobManager(sqlite=sqlite, qdrant=qdrant)

    started = manager.start_job(
        preset_id="embedding_a",
        embedding_client_factory=lambda: FakeEmbeddingClient(dimension=8),
        activate_preset=lambda preset_id: None,
        runner=slow_runner,
    )

    job = started["job"]
    assert job["preset_id"] == "embedding_a"
    assert job["status"] == "pending"
    assert job["stage"] == "queued"
    assert job["total_documents"] == 0
    assert job["processed_documents"] == 0
    assert job["failed_documents"] == []
    assert job["error"] is None
    assert job["started_at"] is not None
    assert job["finished_at"] is None
    stored_job = manager.get_job(job["id"])
    active_job = manager.active_job()
    assert stored_job == job
    assert active_job == job
    assert stored_job is not job
    assert active_job is not job

    job["status"] = "mutated"
    stored_job["stage"] = "mutated"
    active_job["error"] = "mutated"

    latest_job = manager.get_job(job["id"])
    assert latest_job is not None
    assert latest_job["status"] == "pending"
    assert latest_job["stage"] == "queued"
    assert latest_job["error"] is None
    assert isinstance(started["task"], asyncio.Task)
    assert started["task"].done() is False

    release.set()
    await started["task"]


@pytest.mark.asyncio
async def test_start_job_rolls_back_state_when_task_creation_fails(
    sqlite: SQLiteClient, qdrant: QdrantStore, monkeypatch: pytest.MonkeyPatch
):
    original_create_task = asyncio.create_task

    def broken_create_task(coro):
        coro.close()
        raise RuntimeError("task creation failed")

    manager = EmbeddingReindexJobManager(sqlite=sqlite, qdrant=qdrant)
    monkeypatch.setattr(asyncio, "create_task", broken_create_task)

    with pytest.raises(RuntimeError, match="task creation failed"):
        manager.start_job(
            preset_id="embedding_a",
            embedding_client_factory=lambda: FakeEmbeddingClient(dimension=8),
            activate_preset=lambda preset_id: None,
        )

    assert manager.active_job() is None
    assert manager._running_job_id is None
    assert manager._jobs == {}

    monkeypatch.setattr(asyncio, "create_task", original_create_task)
    release = asyncio.Event()

    async def slow_runner(job):
        await release.wait()

    started = manager.start_job(
        preset_id="embedding_b",
        embedding_client_factory=lambda: FakeEmbeddingClient(dimension=8),
        activate_preset=lambda preset_id: None,
        runner=slow_runner,
    )

    release.set()
    await started["task"]


@pytest.mark.asyncio
async def test_run_reindex_job_recreates_collections_and_indexes_documents(
    sqlite: SQLiteClient,
    qdrant: QdrantStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    manager = EmbeddingReindexJobManager(sqlite=sqlite, qdrant=qdrant)
    embedding_client = FakeEmbeddingClient(dimension=6)
    activated_presets: list[str] = []

    await _create_document(
        sqlite,
        tmp_path,
        document_id="d1",
        title="Doc One",
        body="# Doc One\n\n## Section\n\nAlpha\nBeta\nGamma\nDelta\n",
        status="indexed",
    )
    await _create_document(
        sqlite,
        tmp_path,
        document_id="d2",
        title="Doc Two",
        body="# Doc Two\n\n## Section\n\nSecond document body.\n",
        status="raw",
    )

    qdrant.upsert_points(
        ids=["00000000-0000-0000-0000-000000000001"],
        vectors=[[0.2] * 4],
        payloads=[
            {
                "document_id": "stale-doc",
                "chunk_index": 0,
                "title_path": "Stale",
                "text": "stale",
                "video_id": None,
                "start_timestamp": None,
            }
        ],
    )
    qdrant.upsert_summary(
        document_id="stale-doc",
        vector=[0.3] * 4,
        title="Stale",
        brief="stale brief",
    )

    monkeypatch.setattr(
        embedding_reindex_module,
        "get_settings",
        lambda: _fake_settings(chunk_size=12, overlap=0),
        raising=False,
    )

    job = {
        "id": "job-1",
        "preset_id": "embedding_new",
        "status": "running",
        "stage": "probing",
        "total_documents": 0,
        "processed_documents": 0,
        "failed_documents": [],
        "error": None,
    }

    await manager._run_reindex_job(
        job,
        embedding_client_factory=lambda: embedding_client,
        activate_preset=activated_presets.append,
    )

    updated = await sqlite.get_document("d1")
    assert updated is not None
    assert updated["status"] == "indexed"
    assert updated["chunk_count"] == 2
    assert qdrant.collection_vector_size() == 6
    assert qdrant.collection_vector_size(qdrant.SUMMARY_COLLECTION) == 6
    assert qdrant.count_for_document("d1") == 2
    assert qdrant.count_for_document("stale-doc") == 0
    assert qdrant.search_summaries(vector=[0.1] * 6, top_k=5) == []
    assert activated_presets == ["embedding_new"]
    assert embedding_client.seen_texts[0] == [PROBE_TEXT]
    assert job["total_documents"] == 1
    assert job["processed_documents"] == 1
    assert job["failed_documents"] == []
    assert job["status"] == "completed"
    assert job["stage"] == "completed"


@pytest.mark.asyncio
async def test_run_reindex_job_records_document_failure_and_resets_failed_doc(
    sqlite: SQLiteClient,
    qdrant: QdrantStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    manager = EmbeddingReindexJobManager(sqlite=sqlite, qdrant=qdrant)

    good = await _create_document(
        sqlite,
        tmp_path,
        document_id="good-doc",
        title="Good Doc",
        body="# Good Doc\n\n## Section\n\nusable body\n",
        status="indexed",
    )
    bad = await _create_document(
        sqlite,
        tmp_path,
        document_id="bad-doc",
        title="Bad Doc",
        body="# Bad Doc\n\n## Section\n\nmissing soon\n",
        status="indexed",
    )
    Path(bad["file_path"]).unlink()

    monkeypatch.setattr(
        embedding_reindex_module,
        "get_settings",
        lambda: _fake_settings(),
        raising=False,
    )

    job = {
        "id": "job-2",
        "preset_id": "embedding_new",
        "status": "running",
        "stage": "probing",
        "total_documents": 0,
        "processed_documents": 0,
        "failed_documents": [],
        "error": None,
    }

    await manager._run_reindex_job(
        job,
        embedding_client_factory=lambda: FakeEmbeddingClient(dimension=5),
        activate_preset=lambda preset_id: None,
    )

    refreshed_good = await sqlite.get_document(good["id"])
    refreshed_bad = await sqlite.get_document(bad["id"])
    assert refreshed_good is not None
    assert refreshed_bad is not None
    assert refreshed_good["status"] == "indexed"
    assert refreshed_bad["status"] == "raw"
    assert refreshed_bad["chunk_count"] == 0
    assert qdrant.count_for_document(good["id"]) == 1
    assert qdrant.count_for_document(bad["id"]) == 0
    assert job["total_documents"] == 2
    assert job["processed_documents"] == 2
    assert job["status"] == "completed_with_errors"
    assert job["stage"] == "completed_with_errors"
    assert len(job["failed_documents"]) == 1
    failure = job["failed_documents"][0]
    assert failure["document_id"] == "bad-doc"
    assert failure["title"] == "Bad Doc"
    assert "No such file or directory" in failure["error"]
    assert Path(bad["file_path"]).name in failure["error"]


@pytest.mark.asyncio
async def test_run_reindex_job_cleans_main_vectors_when_summary_save_fails(
    sqlite: SQLiteClient,
    qdrant: QdrantStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    manager = EmbeddingReindexJobManager(sqlite=sqlite, qdrant=qdrant)
    document = await _create_document(
        sqlite,
        tmp_path,
        document_id="d1",
        title="Summary Failure Doc",
        body="# Summary Failure Doc\n\n## Section\n\nbody for chunking\n",
        status="indexed",
    )
    await sqlite.set_document_summary(
        document["id"], l2="Long summary", l3="Existing brief"
    )

    async def failing_save_summary(self, **kwargs):
        raise RuntimeError("summary save failed")

    monkeypatch.setattr(
        embedding_reindex_module,
        "get_settings",
        lambda: _fake_settings(),
        raising=False,
    )
    monkeypatch.setattr(
        embedding_reindex_module.DocumentSummaryStore,
        "save_summary",
        failing_save_summary,
    )

    job = {
        "id": "job-summary-fail",
        "preset_id": "embedding_new",
        "status": "running",
        "stage": "probing",
        "total_documents": 0,
        "processed_documents": 0,
        "failed_documents": [],
        "error": None,
    }

    await manager._run_reindex_job(
        job,
        embedding_client_factory=lambda: FakeEmbeddingClient(dimension=5),
        activate_preset=lambda preset_id: None,
    )

    refreshed = await sqlite.get_document(document["id"])
    assert refreshed is not None
    assert refreshed["status"] == "raw"
    assert refreshed["chunk_count"] == 0
    assert qdrant.count_for_document(document["id"]) == 0
    assert job["total_documents"] == 1
    assert job["processed_documents"] == 1
    assert job["status"] == "completed_with_errors"
    assert job["stage"] == "completed_with_errors"
    assert job["failed_documents"] == [
        {
            "document_id": "d1",
            "title": "Summary Failure Doc",
            "error": "summary save failed",
        }
    ]


@pytest.mark.asyncio
async def test_run_reindex_job_rebuilds_existing_summary_vector(
    sqlite: SQLiteClient,
    qdrant: QdrantStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    manager = EmbeddingReindexJobManager(sqlite=sqlite, qdrant=qdrant)
    embedding_client = FakeEmbeddingClient(dimension=7)

    document = await _create_document(
        sqlite,
        tmp_path,
        document_id="d1",
        title="Summary Doc",
        body="# Summary Doc\n\n## Section\n\nsummary source body\n",
        status="indexed",
    )
    await sqlite.set_document_summary(
        document["id"], l2="Long summary", l3="Existing brief"
    )
    qdrant.upsert_summary(
        document_id=document["id"],
        vector=[0.6] * 4,
        title="Summary Doc",
        brief="stale brief",
    )

    monkeypatch.setattr(
        embedding_reindex_module,
        "get_settings",
        lambda: _fake_settings(),
        raising=False,
    )

    job = {
        "id": "job-3",
        "preset_id": "embedding_new",
        "status": "running",
        "stage": "probing",
        "total_documents": 0,
        "processed_documents": 0,
        "failed_documents": [],
        "error": None,
    }

    await manager._run_reindex_job(
        job,
        embedding_client_factory=lambda: embedding_client,
        activate_preset=lambda preset_id: None,
    )

    results = qdrant.search_summaries(vector=[0.1] * 7, top_k=5)
    assert results == [
        {
            "score": pytest.approx(1.0),
            "payload": {
                "document_id": "d1",
                "title": "Summary Doc",
                "brief": "Existing brief",
            },
        }
    ]
    assert embedding_client.seen_texts == [
        [PROBE_TEXT],
        ["Summary Doc > Section\n\nsummary source body"],
        ["Existing brief"],
    ]
    assert job["failed_documents"] == []
