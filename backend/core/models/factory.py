"""Factories for embedding clients and chat models.

API modules import these and keep module-level names so tests can
monkeypatch per-module.
"""

from config.settings import Settings, _is_local_endpoint, get_settings
from core.models.chat_completion import ChatCompletionError
from core.models.chat_model_adapter import (
    ChatCompletionClient,
    SDKChatCompletionClient,
)
from core.rag.embedding import CloudEmbeddingClient


def build_embedding_client(settings: Settings | None = None):
    """Build the embedding client.

    Embedding always uses the OpenAI-compatible protocol (/v1/embeddings),
    regardless of provider (Ollama is reached via its /v1 endpoint, same as
    cloud providers). Local loopback endpoints don't require a real api_key,
    so a placeholder is supplied there -- the Authorization header is ignored
    by local OpenAI-compatible servers.
    """
    embedding = (settings or get_settings()).models.embedding
    api_key = embedding.api_key
    if not api_key and _is_local_endpoint(embedding.endpoint):
        api_key = "local"
    return CloudEmbeddingClient(
        endpoint=embedding.endpoint,
        api_key=api_key,
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


def build_chat_completion_client(
    settings: Settings | None = None,
) -> ChatCompletionClient:
    """Build a sync-compatible client over the SDK-backed chat model path."""
    resolved_settings = settings or get_settings()
    chat = resolved_settings.models.chat
    if not chat.endpoint or not chat.api_key or not chat.model:
        raise ChatCompletionError(
            "Chat model is not configured "
            "(models.chat endpoint/api_key/model required)"
        )
    try:
        return SDKChatCompletionClient(model=build_chat_model(resolved_settings))
    except ValueError as exc:
        raise ChatCompletionError(str(exc)) from exc
