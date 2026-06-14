"""Ollama-native embedding client (POST /api/embed)."""

from typing import Callable

from core.rag.embedding import EmbeddingError, post_json as default_post_json

DEFAULT_OLLAMA_ENDPOINT = "http://localhost:11434"


class OllamaEmbeddingClient:
    def __init__(
        self,
        *,
        endpoint: str | None,
        model: str | None,
        post_json: Callable[..., dict] = default_post_json,
    ) -> None:
        if not model:
            raise EmbeddingError(
                "Ollama embedding model is not configured (models.embedding.model)"
            )
        self.endpoint = (endpoint or DEFAULT_OLLAMA_ENDPOINT).rstrip("/")
        self.model = model
        self.post_json = post_json

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts via the local Ollama server."""
        if not texts:
            return []

        try:
            response = self.post_json(
                f"{self.endpoint}/api/embed",
                {"model": self.model, "input": texts},
                {"Content-Type": "application/json"},
            )
        except OSError as exc:
            raise EmbeddingError(
                f"Ollama unreachable at {self.endpoint} (is `ollama serve` running?)"
            ) from exc

        embeddings = (
            response.get("embeddings") if isinstance(response, dict) else None
        )
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise EmbeddingError("Malformed Ollama embed response")
        return embeddings
