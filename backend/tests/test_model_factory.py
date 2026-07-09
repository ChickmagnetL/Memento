"""Tests for provider-based model client factories."""

import pytest

from config.settings import Settings
from core.models.factory import build_embedding_client, build_chat_model
from core.rag.embedding import CloudEmbeddingClient
from core.rag.ollama_embedding import OllamaEmbeddingClient


def _settings(embedding: dict, chat: dict) -> Settings:
    return Settings(models={"embedding": embedding, "chat": chat})


def test_cloud_embedding_provider_builds_cloud_client():
    settings = _settings(
        {"provider": "cloud", "endpoint": "https://e/v1", "api_key": "k", "model": "m"},
        {"provider": "cloud"},
    )
    client = build_embedding_client(settings)
    assert isinstance(client, CloudEmbeddingClient)


def test_ollama_embedding_provider_builds_ollama_client():
    settings = _settings(
        {"provider": "ollama", "model": "qwen3-embedding:0.6b"},
        {"provider": "cloud"},
    )
    client = build_embedding_client(settings)
    assert isinstance(client, OllamaEmbeddingClient)


def test_ollama_endpoint_builds_ollama_client_regardless_of_provider():
    # localhost:11434 is authoritative -- Ollama even if provider leaked as
    # "ollama" from the default config merge.
    settings = _settings(
        {
            "provider": "ollama",
            "endpoint": "http://localhost:11434",
            "model": "qwen3-embedding:0.6b",
        },
        {"provider": "cloud"},
    )
    client = build_embedding_client(settings)
    assert isinstance(client, OllamaEmbeddingClient)


def test_non_ollama_port_on_localhost_builds_cloud_client():
    # Regression for the 404 bug: an OpenAI-compatible embedding service on
    # localhost:8003 must NOT be treated as Ollama, even though the resolved
    # provider leaks "ollama" from default.yaml.
    settings = _settings(
        {
            "provider": "ollama",
            "endpoint": "http://localhost:8003/v1",
            "api_key": "not-needed",
            "model": "all-MiniLM-L6-v2",
        },
        {"provider": "cloud"},
    )
    client = build_embedding_client(settings)
    assert isinstance(client, CloudEmbeddingClient)


def test_cloud_endpoint_builds_cloud_client_with_leaked_ollama_provider():
    settings = _settings(
        {
            "provider": "ollama",
            "endpoint": "https://api.openai.com/v1",
            "api_key": "sk-x",
            "model": "text-embedding-3-small",
        },
        {"provider": "cloud"},
    )
    client = build_embedding_client(settings)
    assert isinstance(client, CloudEmbeddingClient)


def test_lan_endpoint_builds_cloud_client():
    settings = _settings(
        {
            "provider": "ollama",
            "endpoint": "http://192.168.1.5:8003/v1",
            "api_key": "not-needed",
            "model": "all-MiniLM-L6-v2",
        },
        {"provider": "cloud"},
    )
    client = build_embedding_client(settings)
    assert isinstance(client, CloudEmbeddingClient)


def test_explicit_cloud_provider_honored_even_against_ollama_endpoint():
    # Explicit cloud/openai provider wins for back-compat.
    settings = _settings(
        {
            "provider": "cloud",
            "endpoint": "http://localhost:11434",
            "api_key": "k",
            "model": "m",
        },
        {"provider": "cloud"},
    )
    client = build_embedding_client(settings)
    assert isinstance(client, CloudEmbeddingClient)


def test_chat_model_builds_with_configured_values():
    settings = _settings(
        {"provider": "cloud", "endpoint": "https://e/v1", "api_key": "k", "model": "m"},
        {"endpoint": "http://localhost:11434/v1", "api_key": "ollama", "model": "qwen3"},
    )
    model = build_chat_model(settings)
    assert "qwen3" in repr(model) or getattr(model, "model_name", "") == "qwen3"
