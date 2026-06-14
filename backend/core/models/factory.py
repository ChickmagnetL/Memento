"""Provider-based factories for embedding clients and chat models.

Single switch point for cloud vs ollama. API modules import these and
keep module-level names so tests can monkeypatch per-module.
"""

from config.settings import Settings, get_settings
from core.rag.embedding import CloudEmbeddingClient
from core.rag.ollama_embedding import (
    OllamaEmbeddingClient,
)


def build_embedding_client(settings: Settings | None = None):
    """Build the embedding client according to models.embedding.provider."""
    embedding = (settings or get_settings()).models.embedding
    if embedding.provider == "ollama":
        return OllamaEmbeddingClient(
            endpoint=embedding.endpoint, model=embedding.model
        )
    return CloudEmbeddingClient(
        endpoint=embedding.endpoint,
        api_key=embedding.api_key,
        model=embedding.model,
    )


def build_chat_model(settings: Settings | None = None):
    """Build the pydantic-ai chat model. All providers use the OpenAI
    protocol (/v1/chat/completions). For Ollama, set endpoint to
    http://localhost:11434/v1 and api_key to any non-empty value."""
    from pydantic_ai.models.openai import OpenAIModel
    from pydantic_ai.providers.openai import OpenAIProvider

    chat = (settings or get_settings()).models.chat
    if not chat.api_key or not chat.model:
        raise ValueError(
            "Chat model is not configured (models.chat api_key/model)"
        )
    return OpenAIModel(
        chat.model,
        provider=OpenAIProvider(base_url=chat.endpoint, api_key=chat.api_key),
    )
