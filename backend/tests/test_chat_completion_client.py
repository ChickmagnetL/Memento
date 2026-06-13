"""Tests for the OpenAI-compatible chat completion client."""

import pytest

from core.models.chat_completion import (
    ChatCompletionError,
    CloudChatCompletionClient,
)


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


def test_missing_config_raises_on_init():
    with pytest.raises(ChatCompletionError):
        CloudChatCompletionClient(endpoint=None, api_key="k", model="m")
    with pytest.raises(ChatCompletionError):
        CloudChatCompletionClient(endpoint="https://e", api_key=None, model="m")
    with pytest.raises(ChatCompletionError):
        CloudChatCompletionClient(endpoint="https://e", api_key="k", model=None)
