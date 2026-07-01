"""Adapter for sync chat-completion callers over the SDK-backed chat model."""

import asyncio
from typing import Protocol

from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models import ModelRequestParameters

from core.models.chat_completion import ChatCompletionError

_REQUEST_TIMEOUT_SECONDS = 300


class ChatCompletionClient(Protocol):
    def complete(self, messages: list[dict]) -> str: ...


def _message_content(message: dict) -> str:
    content = message.get("content")
    if not isinstance(content, str):
        raise ChatCompletionError("Malformed chat completion request: content must be a string")
    return content


def _to_model_message(message: dict) -> ModelRequest | ModelResponse:
    role = message.get("role")
    content = _message_content(message)
    if role in {"system", "developer"}:
        return ModelRequest(parts=[SystemPromptPart(content=content)])
    if role == "user":
        return ModelRequest(parts=[UserPromptPart(content=content)])
    if role == "assistant":
        return ModelResponse(parts=[TextPart(content=content)])
    raise ChatCompletionError(f"Malformed chat completion request: unsupported role `{role}`")


def _format_http_error(exc: ModelHTTPError) -> str:
    detail = exc.body
    if isinstance(detail, dict):
        if isinstance(detail.get("message"), str):
            detail = detail["message"]
        else:
            error = detail.get("error")
            if isinstance(error, dict) and isinstance(error.get("message"), str):
                detail = error["message"]
    if detail in (None, ""):
        return str(exc)
    return f"HTTP {exc.status_code}: {detail}"


class SDKChatCompletionClient:
    """Compatibility wrapper exposing ``complete(messages) -> str``."""

    def __init__(self, *, model, model_settings: dict | None = None) -> None:
        self._model = model
        self._model_settings = model_settings or {"timeout": _REQUEST_TIMEOUT_SECONDS}

    def complete(self, messages: list[dict]) -> str:
        try:
            response = asyncio.run(
                self._model.request(
                    [_to_model_message(message) for message in messages],
                    self._model_settings,
                    ModelRequestParameters(),
                )
            )
        except ModelHTTPError as exc:
            raise ChatCompletionError(_format_http_error(exc)) from exc
        except (ModelAPIError, UnexpectedModelBehavior) as exc:
            raise ChatCompletionError(str(exc)) from exc

        content = response.text
        if not isinstance(content, str) or not content.strip():
            raise ChatCompletionError("Malformed chat completion response: empty content")
        return content
