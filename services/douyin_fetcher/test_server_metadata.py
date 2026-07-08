"""Tests for Douyin fetcher metadata extraction."""

import sys
import types

import pytest
from fastapi import HTTPException

from services.douyin_fetcher.server import (
    _build_resolve_payload,
    _use_fake_ms_token_for_f2_import,
)


def test_use_fake_ms_token_for_f2_import(monkeypatch):
    class FakeTokenManager:
        @classmethod
        def gen_false_msToken(cls):
            return "fake-token"

        @classmethod
        def gen_real_msToken(cls):
            raise AssertionError("real msToken should not be used")

    utils_module = types.ModuleType("f2.apps.douyin.utils")
    utils_module.TokenManager = FakeTokenManager

    monkeypatch.setitem(sys.modules, "f2", types.ModuleType("f2"))
    monkeypatch.setitem(sys.modules, "f2.apps", types.ModuleType("f2.apps"))
    monkeypatch.setitem(
        sys.modules,
        "f2.apps.douyin",
        types.ModuleType("f2.apps.douyin"),
    )
    monkeypatch.setitem(sys.modules, "f2.apps.douyin.utils", utils_module)

    _use_fake_ms_token_for_f2_import()

    assert FakeTokenManager.gen_real_msToken() == "fake-token"


def test_build_resolve_payload_includes_metadata():
    detail = {
        "desc": "视频标题",
        "author": {"nickname": "作者", "sec_uid": "sec-user"},
        "video": {
            "duration": 42000,
            "play_addr": {"url_list": ["https://cdn.example.com/video.mp4"]},
        },
    }

    assert _build_resolve_payload(detail) == {
        "video_url": "https://cdn.example.com/video.mp4",
        "title": "视频标题",
        "author": "作者",
        "author_id": "sec-user",
        "duration": 42,
    }


def test_build_resolve_payload_removes_hashtag_topics_from_title():
    detail = {
        "desc": "真实标题 #随带话题 #另一个话题",
        "author": {"nickname": "作者", "sec_uid": "sec-user"},
        "video": {
            "duration": 42000,
            "play_addr": {"url_list": ["https://cdn.example.com/video.mp4"]},
        },
    }

    assert _build_resolve_payload(detail)["title"] == "真实标题"


def test_build_resolve_payload_returns_none_when_desc_only_has_topics():
    detail = {
        "desc": "#随带话题 #另一个话题",
        "author": {"nickname": "作者", "sec_uid": "sec-user"},
        "video": {
            "duration": 42000,
            "play_addr": {"url_list": ["https://cdn.example.com/video.mp4"]},
        },
    }

    assert _build_resolve_payload(detail)["title"] is None


def test_build_resolve_payload_keeps_hash_inside_title_word():
    detail = {
        "desc": "F#语言 #编程",
        "author": {"nickname": "作者", "sec_uid": "sec-user"},
        "video": {
            "duration": 42000,
            "play_addr": {"url_list": ["https://cdn.example.com/video.mp4"]},
        },
    }

    assert _build_resolve_payload(detail)["title"] == "F#语言"


def test_build_resolve_payload_removes_topic_without_leading_space():
    detail = {
        "desc": "真实标题#随带话题",
        "author": {"nickname": "作者", "sec_uid": "sec-user"},
        "video": {
            "duration": 42000,
            "play_addr": {"url_list": ["https://cdn.example.com/video.mp4"]},
        },
    }

    assert _build_resolve_payload(detail)["title"] == "真实标题"


def test_build_resolve_payload_defaults_missing_metadata_to_none():
    detail = {
        "video": {
            "play_addr": {"url_list": ["https://cdn.example.com/video.mp4"]},
        },
    }

    assert _build_resolve_payload(detail) == {
        "video_url": "https://cdn.example.com/video.mp4",
        "title": None,
        "author": None,
        "author_id": None,
        "duration": None,
    }


def test_build_resolve_payload_ignores_malformed_optional_metadata():
    detail = {
        "desc": ["not", "a", "string"],
        "author": "not-an-author-object",
        "video": {
            "duration": True,
            "play_addr": {"url_list": ["https://cdn.example.com/video.mp4"]},
        },
    }

    assert _build_resolve_payload(detail) == {
        "video_url": "https://cdn.example.com/video.mp4",
        "title": None,
        "author": None,
        "author_id": None,
        "duration": None,
    }


def test_build_resolve_payload_handles_non_dict_video_as_missing_url():
    detail = {
        "desc": "视频标题",
        "author": {"nickname": "作者", "sec_uid": "sec-user"},
        "video": "not-a-video-object",
    }

    with pytest.raises(HTTPException, match="No playable video URL"):
        _build_resolve_payload(detail)
