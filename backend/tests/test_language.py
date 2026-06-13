"""Tests for ASR language selection."""

from core.video.language import detect_asr_language


def test_cjk_title_routes_to_zh():
    assert detect_asr_language("青蒿素的发现历程", override="auto") == "zh"


def test_latin_title_routes_to_en():
    assert detect_asr_language("Introduction to Rust", override="auto") == "en"


def test_mixed_title_routes_to_zh():
    assert detect_asr_language("Rust 入门教程", override="auto") == "zh"


def test_override_wins():
    assert detect_asr_language("青蒿素", override="en") == "en"
    assert detect_asr_language("hello", override="zh") == "zh"
