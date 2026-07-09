"""Tests for the endpoint-based embedding client factory."""

from config.settings import Settings
from core.models.factory import build_embedding_client, build_chat_model
from core.rag.embedding import CloudEmbeddingClient


def _settings(embedding: dict, chat: dict) -> Settings:
    return Settings(models={"embedding": embedding, "chat": chat})


def test_cloud_endpoint_builds_cloud_client():
    settings = _settings(
        {"endpoint": "https://e/v1", "api_key": "k", "model": "m"},
        {},
    )
    client = build_embedding_client(settings)
    assert isinstance(client, CloudEmbeddingClient)


def test_local_ollama_endpoint_builds_cloud_client():
    # Ollama is reached via its OpenAI-compatible /v1 endpoint; local
    # loopback needs no real api_key (a placeholder is injected).
    settings = _settings(
        {"endpoint": "http://localhost:11434/v1", "model": "qwen3-embedding:0.6b"},
        {},
    )
    client = build_embedding_client(settings)
    assert isinstance(client, CloudEmbeddingClient)
    assert client.api_key == "local"


def test_non_ollama_port_on_localhost_builds_cloud_client():
    # An OpenAI-compatible embedding service on localhost:8003 must NOT be
    # treated as Ollama -- only port 11434 selects the Ollama protocol.
    settings = _settings(
        {
            "endpoint": "http://localhost:8003/v1",
            "api_key": "not-needed",
            "model": "all-MiniLM-L6-v2",
        },
        {},
    )
    client = build_embedding_client(settings)
    assert isinstance(client, CloudEmbeddingClient)


def test_cloud_endpoint_builds_cloud_client():
    settings = _settings(
        {
            "endpoint": "https://api.openai.com/v1",
            "api_key": "sk-x",
            "model": "text-embedding-3-small",
        },
        {},
    )
    client = build_embedding_client(settings)
    assert isinstance(client, CloudEmbeddingClient)


def test_lan_endpoint_builds_cloud_client():
    settings = _settings(
        {
            "endpoint": "http://192.168.1.5:8003/v1",
            "api_key": "not-needed",
            "model": "all-MiniLM-L6-v2",
        },
        {},
    )
    client = build_embedding_client(settings)
    assert isinstance(client, CloudEmbeddingClient)


def test_chat_model_builds_with_configured_values():
    settings = _settings(
        {},
        {"endpoint": "http://localhost:11434/v1", "api_key": "ollama", "model": "qwen3"},
    )
    model = build_chat_model(settings)
    assert "qwen3" in repr(model) or getattr(model, "model_name", "") == "qwen3"
