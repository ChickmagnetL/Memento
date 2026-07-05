"""Tests for QdrantStore chunk persistence (embedded mode, tmp dir)."""

from pathlib import Path

import pytest
from qdrant_client.models import Distance

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


def _collection_distance(store: QdrantStore, name: str | None = None) -> Distance:
    collection_name = store.collection_name if name is None else name
    info = store._require_client().get_collection(collection_name)
    return info.config.params.vectors.distance


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


def test_search_points_returns_payload_and_score_ordered(store: QdrantStore):
    store.upsert_points(
        ids=[
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        ],
        vectors=[[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]],
        payloads=[_payload("d1", 0), _payload("d1", 1)],
    )

    results = store.search_points(vector=[1.0, 0.0, 0.0, 0.0], top_k=2)

    assert len(results) == 2
    # Closest vector first.
    assert results[0]["payload"]["chunk_index"] == 0
    assert results[0]["score"] >= results[1]["score"]
    assert results[0]["payload"]["text"] == "chunk 0"


def test_search_points_respects_top_k(store: QdrantStore):
    store.upsert_points(
        ids=[
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        ],
        vectors=[[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]],
        payloads=[_payload("d1", 0), _payload("d1", 1)],
    )

    assert len(store.search_points(vector=[1.0, 0.0, 0.0, 0.0], top_k=1)) == 1


def test_scroll_all_points_returns_all_payloads(store: QdrantStore):
    store.upsert_points(
        ids=[
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        ],
        vectors=[[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]],
        payloads=[_payload("d1", 0), _payload("d1", 1)],
    )

    payloads = store.scroll_all_points()

    assert len(payloads) == 2
    assert {p["chunk_index"] for p in payloads} == {0, 1}


def test_scroll_all_points_empty_collection(store: QdrantStore):
    assert store.scroll_all_points() == []


def test_summary_collection_upsert_and_search(store: QdrantStore):
    store.ensure_summary_collection(vector_size=8)
    store.upsert_summary(
        document_id="d1",
        vector=[0.1] * 8,
        title="React Hooks",
        brief="useState introduction",
    )
    results = store.search_summaries(vector=[0.1] * 8, top_k=5)
    assert len(results) >= 1
    assert len(results) <= 5
    assert any(r["payload"]["document_id"] == "d1" for r in results)
    match = next(r for r in results if r["payload"]["document_id"] == "d1")
    assert match["payload"]["title"] == "React Hooks"
    assert match["payload"]["brief"] == "useState introduction"


def test_collection_vector_size_returns_existing_dimension(store: QdrantStore):
    assert store.collection_vector_size("documents") == 4


def test_collection_vector_size_defaults_to_store_collection(store: QdrantStore):
    assert store.collection_vector_size() == 4


def test_collection_vector_size_returns_none_for_missing_collection(
    store: QdrantStore,
):
    assert store.collection_vector_size("missing") is None


def test_recreate_collection_replaces_dimension_and_clears_points(
    store: QdrantStore,
):
    store.upsert_points(
        ids=["11111111-1111-1111-1111-111111111111"],
        vectors=[[0.1, 0.2, 0.3, 0.4]],
        payloads=[_payload("d1", 0)],
    )
    assert store.count_for_document("d1") == 1

    store.recreate_collection("documents", vector_size=8)

    assert store.collection_vector_size("documents") == 8
    assert store.scroll_all_points() == []


def test_recreate_collection_without_name_replaces_default_collection_with_cosine_distance(
    store: QdrantStore,
):
    store.upsert_points(
        ids=["11111111-1111-1111-1111-111111111111"],
        vectors=[[0.1, 0.2, 0.3, 0.4]],
        payloads=[_payload("d1", 0)],
    )

    store.recreate_collection(vector_size=8)

    assert store.collection_vector_size() == 8
    assert store.scroll_all_points() == []
    assert _collection_distance(store) == Distance.COSINE


def test_recreate_summary_collection_replaces_dimension(store: QdrantStore):
    store.ensure_summary_collection(vector_size=4)
    assert store.collection_vector_size(QdrantStore.SUMMARY_COLLECTION) == 4

    store.recreate_summary_collection(vector_size=8)

    assert store.collection_vector_size(QdrantStore.SUMMARY_COLLECTION) == 8


def test_recreate_summary_collection_uses_cosine_distance(store: QdrantStore):
    store.ensure_summary_collection(vector_size=4)

    store.recreate_summary_collection(vector_size=8)

    assert _collection_distance(store, QdrantStore.SUMMARY_COLLECTION) == Distance.COSINE
