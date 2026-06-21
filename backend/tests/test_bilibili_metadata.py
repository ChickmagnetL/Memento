"""Tests for Bilibili video metadata fetching."""

import pytest

from core.video.bilibili import BilibiliSubtitleClient


def test_fetch_metadata_parses_view_response():
    calls = []

    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        calls.append((url, referer, cookie))
        return {
            "code": 0,
            "data": {
                "title": "真实标题",
                "duration": 123,
                "owner": {"name": "作者名", "mid": 456789},
            },
        }

    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json, cookie="SESSDATA=secret")

    assert client.fetch_metadata("BV1abcDEF234") == {
        "title": "真实标题",
        "author": "作者名",
        "author_id": "456789",
        "duration": 123,
    }
    assert calls == [
        (
            "https://api.bilibili.com/x/web-interface/view?bvid=BV1abcDEF234",
            None,
            None,
        )
    ]


def test_fetch_metadata_returns_none_for_nonzero_code():
    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        return {"code": -404, "message": "啥都木有"}

    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json)

    assert client.fetch_metadata("BV1abcDEF234") is None


def test_fetch_metadata_returns_none_for_os_error():
    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        raise OSError("network down")

    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json)

    assert client.fetch_metadata("BV1abcDEF234") is None


def test_fetch_metadata_returns_none_for_malformed_response():
    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        return {"code": 0, "data": {"title": "缺少 owner"}}

    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json)

    assert client.fetch_metadata("BV1abcDEF234") is None


@pytest.mark.parametrize(
    "data",
    [
        {"title": 123, "duration": 123, "owner": {"name": "作者名", "mid": 456789}},
        {"title": "真实标题", "duration": "123", "owner": {"name": "作者名", "mid": 456789}},
        {"title": "真实标题", "duration": True, "owner": {"name": "作者名", "mid": 456789}},
        {"title": "真实标题", "duration": 123, "owner": {"name": 123, "mid": 456789}},
        {"title": "真实标题", "duration": 123, "owner": {"name": "作者名", "mid": None}},
        {"title": "真实标题", "duration": 123, "owner": {"name": "作者名", "mid": True}},
    ],
)
def test_fetch_metadata_returns_none_for_malformed_leaf_field_types(data):
    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        return {"code": 0, "data": data}

    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json)

    assert client.fetch_metadata("BV1abcDEF234") is None
