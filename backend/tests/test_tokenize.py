"""Tests for Chinese-aware tokenization."""

from core.rag.tokenize import tokenize


def test_tokenize_chinese_splits_words():
    tokens = tokenize("视频知识库助手")
    assert len(tokens) >= 2
    assert "视频" in tokens
    assert "助手" in tokens


def test_tokenize_filters_whitespace_and_punctuation():
    tokens = tokenize("你好，世界！ hello world")
    assert "，" not in tokens
    assert "！" not in tokens
    assert " " not in tokens
    assert "hello" in tokens
    assert "world" in tokens


def test_tokenize_empty_returns_empty():
    assert tokenize("   ") == []


def test_tokenize_empty_string():
    assert tokenize("") == []


def test_tokenize_pure_punctuation():
    tokens = tokenize("，。！？")
    assert tokens == []
