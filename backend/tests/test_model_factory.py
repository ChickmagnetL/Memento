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


def test_chat_model_builds_with_configured_values():
    settings = _settings(
        {"provider": "cloud", "endpoint": "https://e/v1", "api_key": "k", "model": "m"},
        {"endpoint": "http://localhost:11434/v1", "api_key": "ollama", "model": "qwen3"},
    )
    model = build_chat_model(settings)
    assert "qwen3" in repr(model) or getattr(model, "model_name", "") == "qwen3"
