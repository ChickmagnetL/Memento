"""Tests for the OpenAI-compatible embedding client."""

import pytest

from core.rag.embedding import CloudEmbeddingClient, EmbeddingError


def test_embed_posts_batch_and_returns_vectors_in_order():
    calls = []

    def fake_post_json(url: str, payload: dict, headers: dict) -> dict:
        calls.append((url, payload, headers))
        # Return embeddings out of order to verify index-based sorting.
        return {
            "data": [
                {"index": 1, "embedding": [0.3, 0.4]},
                {"index": 0, "embedding": [0.1, 0.2]},
            ]
        }

    client = CloudEmbeddingClient(
        endpoint="https://api.example.com/v1",
        api_key="sk-test",
        model="text-embedding-test",
        post_json=fake_post_json,
    )

    vectors = client.embed(["第一段", "第二段"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    url, payload, headers = calls[0]
    assert url == "https://api.example.com/v1/embeddings"
    assert payload == {
        "model": "text-embedding-test",
        "input": ["第一段", "第二段"],
    }
    assert headers["Authorization"] == "Bearer sk-test"


def test_embed_empty_input_returns_empty_without_request():
    def fail_post_json(url, payload, headers):
        raise AssertionError("should not be called")

    client = CloudEmbeddingClient(
        endpoint="https://api.example.com/v1",
        api_key="sk-test",
        model="m",
        post_json=fail_post_json,
    )
    assert client.embed([]) == []


def test_embed_malformed_response_raises_embedding_error():
    client = CloudEmbeddingClient(
        endpoint="https://api.example.com/v1",
        api_key="sk-test",
        model="m",
        post_json=lambda url, payload, headers: {"unexpected": True},
    )
    with pytest.raises(EmbeddingError):
        client.embed(["text"])


def test_missing_config_raises_embedding_error_on_init():
    with pytest.raises(EmbeddingError):
        CloudEmbeddingClient(endpoint=None, api_key="k", model="m")
    with pytest.raises(EmbeddingError):
        CloudEmbeddingClient(endpoint="https://e", api_key="k", model=None)