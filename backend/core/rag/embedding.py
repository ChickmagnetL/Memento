"""OpenAI-compatible embedding client.

Talks to any /v1/embeddings endpoint (DeepSeek, SiliconFlow, OpenAI...).
The HTTP call is injectable for tests, mirroring core.video.bilibili.
"""

import json
from typing import Callable
from urllib.request import Request, urlopen


class EmbeddingError(Exception):
    pass


def post_json(url: str, payload: dict, headers: dict, *, timeout: int = 30) -> dict:
    """POST a JSON payload and return the decoded JSON response."""
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers=headers, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class CloudEmbeddingClient:
    def __init__(
        self,
        *,
        endpoint: str | None,
        api_key: str | None,
        model: str | None,
        post_json: Callable[[str, dict, dict], dict] = post_json,
    ) -> None:
        if not endpoint or not api_key or not model:
            raise EmbeddingError(
                "Embedding model is not configured "
                "(models.embedding endpoint/api_key/model required)"
            )
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.post_json = post_json

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts, preserving input order."""
        if not texts:
            return []

        response = self.post_json(
            f"{self.endpoint}/embeddings",
            {"model": self.model, "input": texts},
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        data = response.get("data") if isinstance(response, dict) else None
        if not isinstance(data, list) or len(data) != len(texts):
            raise EmbeddingError("Malformed embedding API response")

        vectors: list[list[float] | None] = [None] * len(texts)
        for item in data:
            if not isinstance(item, dict):
                raise EmbeddingError("Malformed embedding API response")
            index = item.get("index")
            embedding = item.get("embedding")
            if not isinstance(index, int) or not isinstance(embedding, list):
                raise EmbeddingError("Malformed embedding API response")
            if index < 0 or index >= len(texts):
                raise EmbeddingError("Malformed embedding API response")
            vectors[index] = embedding
        if any(v is None for v in vectors):
            raise EmbeddingError("Malformed embedding API response")
        return vectors  # type: ignore[return-value]