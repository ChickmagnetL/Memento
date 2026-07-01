"""OpenAI-compatible chat completion client.

Same injectable-HTTP pattern as core.rag.embedding. Used by transcript
cleaning (2D); the chat agent (4A) uses pydantic-ai instead.
"""

import time
from typing import Callable

from core.rag.embedding import EmbeddingError, post_json as default_post_json

_MAX_COMPLETION_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 1.0


class ChatCompletionError(Exception):
    pass


class CloudChatCompletionClient:
    def __init__(
        self,
        *,
        endpoint: str | None,
        api_key: str | None,
        model: str | None,
        post_json: Callable[[str, dict, dict], dict] = default_post_json,
    ) -> None:
        if not endpoint or not api_key or not model:
            raise ChatCompletionError(
                "Chat model is not configured "
                "(models.chat endpoint/api_key/model required)"
            )
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.post_json = post_json

    def complete(self, messages: list[dict]) -> str:
        """Run one chat completion and return the assistant message text."""
        for attempt in range(_MAX_COMPLETION_ATTEMPTS):
            try:
                response = self.post_json(
                    f"{self.endpoint}/chat/completions",
                    {"model": self.model, "messages": messages},
                    {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
                break
            except EmbeddingError as exc:
                if attempt == _MAX_COMPLETION_ATTEMPTS - 1:
                    raise ChatCompletionError(str(exc)) from exc
                time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))

        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ChatCompletionError(
                "Malformed chat completion response"
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise ChatCompletionError("Malformed chat completion response: empty content")
        return content
