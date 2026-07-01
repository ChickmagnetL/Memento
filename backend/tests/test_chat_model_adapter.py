"""Tests for the SDK-backed chat completion adapter."""

from types import SimpleNamespace

import pytest
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)

from api import documents
from core.models.chat_completion import ChatCompletionError
from core.models.chat_model_adapter import SDKChatCompletionClient
import core.models.factory as factory_module
from core.rag import document_summary_store as summary_module


class FakeModel:
    def __init__(self, *, response=None, error=None) -> None:
        self.calls = []
        self._response = response
        self._error = error

    async def request(self, messages, model_settings, model_request_parameters):
        self.calls.append((messages, model_settings, model_request_parameters))
        if self._error is not None:
            raise self._error
        return self._response


def _settings(*, endpoint="https://api.example.com/v1", api_key="sk-test", model="test-chat"):
    return SimpleNamespace(
        models=SimpleNamespace(
            chat=SimpleNamespace(endpoint=endpoint, api_key=api_key, model=model)
        )
    )


def test_sdk_chat_completion_client_uses_sdk_request():
    fake_model = FakeModel(
        response=ModelResponse(parts=[TextPart(content="清洗后的文本")], model_name="m")
    )
    client = SDKChatCompletionClient(model=fake_model)

    content = client.complete(
        [
            {"role": "system", "content": "you clean transcripts"},
            {"role": "user", "content": "原始文本"},
        ]
    )

    assert content == "清洗后的文本"
    messages, model_settings, _params = fake_model.calls[0]
    assert model_settings == {"timeout": 300}
    assert isinstance(messages[0], ModelRequest)
    assert isinstance(messages[0].parts[0], SystemPromptPart)
    assert messages[0].parts[0].content == "you clean transcripts"
    assert isinstance(messages[1], ModelRequest)
    assert isinstance(messages[1].parts[0], UserPromptPart)
    assert messages[1].parts[0].content == "原始文本"


def test_sdk_chat_completion_client_maps_model_http_errors():
    client = SDKChatCompletionClient(
        model=FakeModel(error=ModelHTTPError(524, "test-chat", "upstream timeout"))
    )

    with pytest.raises(ChatCompletionError, match="HTTP 524: upstream timeout"):
        client.complete([{"role": "user", "content": "原始文本"}])


def test_factory_build_chat_completion_client_uses_chat_model_path(monkeypatch):
    fake_model = FakeModel(
        response=ModelResponse(parts=[TextPart(content="摘要")], model_name="m")
    )
    monkeypatch.setattr(
        factory_module, "build_chat_model", lambda settings=None: fake_model
    )

    client = factory_module.build_chat_completion_client(_settings())

    assert client.complete([{"role": "user", "content": "文档"}]) == "摘要"
    assert fake_model.calls


def test_factory_build_chat_completion_client_requires_full_chat_config():
    with pytest.raises(
        ChatCompletionError,
        match="models.chat endpoint/api_key/model required",
    ):
        factory_module.build_chat_completion_client(_settings(endpoint=None))


def test_documents_build_chat_completion_client_delegates_to_factory(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(
        documents, "factory_build_chat_completion_client", lambda: sentinel
    )

    assert documents.build_chat_completion_client() is sentinel


def test_document_summary_store_build_chat_completion_client_delegates_to_factory(
    monkeypatch,
):
    sentinel = object()
    monkeypatch.setattr(
        summary_module, "factory_build_chat_completion_client", lambda: sentinel
    )

    assert summary_module._build_chat_completion_client() is sentinel
