"""Tests for the Ollama embedding client."""

import pytest

from core.rag.embedding import EmbeddingError
from core.rag.ollama_embedding import OllamaEmbeddingClient


def test_embed_posts_to_ollama_api_and_returns_vectors():
    calls = []

    def fake_post_json(url, payload, headers, timeout=30):
        calls.append((url, payload))
        return {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}

    client = OllamaEmbeddingClient(
        endpoint="http://localhost:11434",
        model="qwen3-embedding:0.6b",
        post_json=fake_post_json,
    )

    vectors = client.embed(["第一段", "第二段"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    url, payload = calls[0]
    assert url == "http://localhost:11434/api/embed"
    assert payload == {
        "model": "qwen3-embedding:0.6b",
        "input": ["第一段", "第二段"],
    }


def test_embed_empty_returns_empty_without_request():
    client = OllamaEmbeddingClient(
        endpoint="http://localhost:11434",
        model="m",
        post_json=lambda url, payload, headers, timeout=30: pytest.fail("no call"),
    )
    assert client.embed([]) == []


def test_embed_malformed_response_raises():
    client = OllamaEmbeddingClient(
        endpoint="http://localhost:11434",
        model="m",
        post_json=lambda url, payload, headers, timeout=30: {"bad": 1},
    )
    with pytest.raises(EmbeddingError):
        client.embed(["x"])


def test_connection_error_wrapped_with_hint():
    def failing(url, payload, headers, timeout=30):
        raise OSError("connection refused")

    client = OllamaEmbeddingClient(
        endpoint="http://localhost:11434", model="m", post_json=failing
    )
    with pytest.raises(EmbeddingError, match="Ollama"):
        client.embed(["x"])


def test_missing_config_raises_on_init():
    with pytest.raises(EmbeddingError):
        OllamaEmbeddingClient(endpoint="http://localhost:11434", model=None)
