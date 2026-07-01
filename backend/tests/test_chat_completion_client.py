"""Tests for the OpenAI-compatible chat completion client."""

import pytest

import core.models.chat_completion as chat_completion
from core.models.chat_completion import (
    ChatCompletionError,
    CloudChatCompletionClient,
)
from core.rag.embedding import EmbeddingError


def test_complete_posts_messages_and_returns_content():
    calls = []

    def fake_post_json(url: str, payload: dict, headers: dict) -> dict:
        calls.append((url, payload, headers))
        return {"choices": [{"message": {"content": "清洗后的文本"}}]}

    client = CloudChatCompletionClient(
        endpoint="https://api.example.com/v1",
        api_key="sk-test",
        model="test-chat",
        post_json=fake_post_json,
    )

    content = client.complete(
        [
            {"role": "system", "content": "you clean transcripts"},
            {"role": "user", "content": "原始文本"},
        ]
    )

    assert content == "清洗后的文本"
    url, payload, headers = calls[0]
    assert url == "https://api.example.com/v1/chat/completions"
    assert payload["model"] == "test-chat"
    assert payload["messages"][1]["content"] == "原始文本"
    assert headers["Authorization"] == "Bearer sk-test"


def test_complete_malformed_response_raises():
    client = CloudChatCompletionClient(
        endpoint="https://api.example.com/v1",
        api_key="sk-test",
        model="m",
        post_json=lambda url, payload, headers: {"unexpected": True},
    )
    with pytest.raises(ChatCompletionError):
        client.complete([{"role": "user", "content": "x"}])


def test_complete_rejects_empty_or_whitespace_content():
    client = CloudChatCompletionClient(
        endpoint="https://api.example.com/v1",
        api_key="sk-test",
        model="m",
        post_json=lambda url, payload, headers: {"choices": [{"message": {"content": ""}}]},
    )
    with pytest.raises(ChatCompletionError):
        client.complete([{"role": "user", "content": "x"}])

    client = CloudChatCompletionClient(
        endpoint="https://api.example.com/v1",
        api_key="sk-test",
        model="m",
        post_json=lambda url, payload, headers: {"choices": [{"message": {"content": "   "}}]},
    )
    with pytest.raises(ChatCompletionError):
        client.complete([{"role": "user", "content": "x"}])

    client = CloudChatCompletionClient(
        endpoint="https://api.example.com/v1",
        api_key="sk-test",
        model="m",
        post_json=lambda url, payload, headers: {"choices": [{"message": {"content": None}}]},
    )
    with pytest.raises(ChatCompletionError):
        client.complete([{"role": "user", "content": "x"}])


@pytest.mark.parametrize(
    "error_message",
    [
        "HTTP 429: rate limited",
        "HTTP 524: upstream timeout",
        "HTTP 402: Payment Required",
        "HTTP request failed: timed out",
    ],
)
def test_complete_retries_upstream_request_errors_then_returns_content(
    monkeypatch, error_message
):
    attempts = []
    sleeps = []

    def fake_post_json(url: str, payload: dict, headers: dict) -> dict:
        attempts.append((url, payload, headers))
        if len(attempts) < 3:
            raise EmbeddingError(error_message)
        return {"choices": [{"message": {"content": "清洗后的文本"}}]}

    monkeypatch.setattr(chat_completion.time, "sleep", sleeps.append)

    client = CloudChatCompletionClient(
        endpoint="https://api.example.com/v1",
        api_key="sk-test",
        model="m",
        post_json=fake_post_json,
    )

    content = client.complete([{"role": "user", "content": "x"}])

    assert content == "清洗后的文本"
    assert len(attempts) == 3
    assert sleeps == [1.0, 2.0]


def test_complete_wraps_upstream_request_errors_as_chat_completion_error_after_retries(monkeypatch):
    attempts = []
    sleeps = []

    def fake_post_json(url: str, payload: dict, headers: dict) -> dict:
        attempts.append((url, payload, headers))
        raise EmbeddingError("HTTP 524: upstream timeout")

    monkeypatch.setattr(chat_completion.time, "sleep", sleeps.append)

    client = CloudChatCompletionClient(
        endpoint="https://api.example.com/v1",
        api_key="sk-test",
        model="m",
        post_json=fake_post_json,
    )

    with pytest.raises(ChatCompletionError, match="HTTP 524: upstream timeout"):
        client.complete([{"role": "user", "content": "x"}])

    assert len(attempts) == 3
    assert sleeps == [1.0, 2.0]


def test_missing_config_raises_on_init():
    with pytest.raises(ChatCompletionError):
        CloudChatCompletionClient(endpoint=None, api_key="k", model="m")
    with pytest.raises(ChatCompletionError):
        CloudChatCompletionClient(endpoint="https://e", api_key=None, model="m")
    with pytest.raises(ChatCompletionError):
        CloudChatCompletionClient(endpoint="https://e", api_key="k", model=None)
