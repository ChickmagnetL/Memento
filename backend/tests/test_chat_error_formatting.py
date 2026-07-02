"""Unit tests for the chat SSE error message formatter."""

import asyncio

from pydantic_ai.exceptions import ModelHTTPError

from api.chat import _format_chat_error


def test_model_http_error_with_nested_error_message():
    exc = ModelHTTPError(
        status_code=402,
        model_name="x",
        body={"error": {"message": "Insufficient balance"}},
    )
    assert _format_chat_error(exc) == "HTTP 402: Insufficient balance"


def test_model_http_error_with_top_level_message():
    exc = ModelHTTPError(
        status_code=402,
        model_name="x",
        body={"message": "Insufficient balance"},
    )
    assert _format_chat_error(exc) == "HTTP 402: Insufficient balance"


def test_model_http_error_without_body():
    exc = ModelHTTPError(status_code=500, model_name="x", body=None)
    assert _format_chat_error(exc) == "HTTP 500"


def test_model_http_error_with_body_dict_but_no_message():
    exc = ModelHTTPError(
        status_code=400,
        model_name="x",
        body={"error": {}},
    )
    assert _format_chat_error(exc) == "HTTP 400"


def test_timeout_error_empty_str_falls_back_to_class_name():
    exc = asyncio.TimeoutError()
    # asyncio.TimeoutError() has an empty str(); fall back to the class name.
    assert _format_chat_error(exc) in ("TimeoutError", "asyncio.TimeoutError")


def test_generic_exception_with_non_empty_str():
    exc = RuntimeError("boom")
    assert _format_chat_error(exc) == "boom"
