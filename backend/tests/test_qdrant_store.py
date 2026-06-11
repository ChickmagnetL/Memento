"""Tests for QdrantStore chunk persistence (embedded mode, tmp dir)."""

from pathlib import Path

import pytest

from storage.qdrant_client import QdrantStore


@pytest.fixture
def store(tmp_path: Path):
    store = QdrantStore(tmp_path / "qdrant")
    store.connect(vector_size=4)
    try:
        yield store
    finally:
        store.close()


def _payload(document_id: str, index: int) -> dict:
    return {
        "video_id": "v1",
        "document_id": document_id,
        "chunk_index": index,
        "title_path": "标题 > Transcript",
        "text": f"chunk {index}",
        "start_timestamp": "00:01",
    }


def test_upsert_and_count(store: QdrantStore):
    store.upsert_points(
        ids=["11111111-1111-1111-1111-111111111111"],
        vectors=[[0.1, 0.2, 0.3, 0.4]],
        payloads=[_payload("d1", 0)],
    )
    assert store.count_for_document("d1") == 1


def test_delete_for_document_removes_only_that_document(store: QdrantStore):
    store.upsert_points(
        ids=[
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        ],
        vectors=[[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]],
        payloads=[_payload("d1", 0), _payload("d2", 0)],
    )

    store.delete_for_document("d1")

    assert store.count_for_document("d1") == 0
    assert store.count_for_document("d2") == 1


def test_operations_require_connection(tmp_path: Path):
    store = QdrantStore(tmp_path / "qdrant")
    with pytest.raises(RuntimeError):
        store.upsert_points(ids=[], vectors=[], payloads=[])


def test_upsert_mismatched_lengths_raises_value_error(store: QdrantStore):
    with pytest.raises(ValueError):
        store.upsert_points(
            ids=["id1", "id2"],
            vectors=[[0.1, 0.2, 0.3, 0.4]],
            payloads=[_payload("d1", 0)],
        )