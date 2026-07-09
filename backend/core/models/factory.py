"""Provider-based factories for embedding clients and chat models.

Single switch point for cloud vs ollama. API modules import these and
keep module-level names so tests can monkeypatch per-module.
"""

from urllib.parse import urlparse

from config.settings import Settings, get_settings
from core.models.chat_completion import ChatCompletionError
from core.models.chat_model_adapter import (
    ChatCompletionClient,
    SDKChatCompletionClient,
)
from core.rag.embedding import CloudEmbeddingClient
from core.rag.ollama_embedding import (
    OllamaEmbeddingClient,
)


def _looks_like_ollama_endpoint(endpoint: str | None) -> bool:
    """Return True only when *endpoint* points at a local Ollama daemon
    (localhost/127.0.0.1/::1 on port 11434). Mirrors the endpoint check in
    backend/api/settings.py:_is_ollama_model_list_config so the embedding
    client and the model-list fetch agree on what counts as Ollama.
    """
    if not endpoint:
        return False
    try:
        parsed = urlparse(endpoint)
    except ValueError:
        return False
    return (
        parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        and parsed.port == 11434
    )


def build_embedding_client(settings: Settings | None = None):
    """Build the embedding client.

    Protocol selection mirrors backend/api/settings.py:_is_ollama_model_list_config:
    the endpoint is authoritative when present -- localhost:11434 means Ollama,
    anything else means an OpenAI-compatible (cloud) service. This makes
    ``provider`` decorative, matching the Settings UI which intentionally omits
    the field. An explicit ``cloud``/``openai`` provider is still honored for
    back-compat; when no endpoint is set, ``provider`` is used as a fallback.
    """
    embedding = (settings or get_settings()).models.embedding
    if embedding.provider in {"cloud", "openai"}:
        use_ollama = False
    elif embedding.endpoint:
        use_ollama = _looks_like_ollama_endpoint(embedding.endpoint)
    else:
        use_ollama = embedding.provider == "ollama"

    if use_ollama:
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
