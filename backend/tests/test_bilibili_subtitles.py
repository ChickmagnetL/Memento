"""Tests for the Bilibili soft subtitle client."""

import pytest

from core.video import bilibili
from core.video.bilibili import (
    BilibiliSubtitleClient,
    BilibiliSubtitleError,
    SubtitleEntry,
    extract_bvid,
)


def test_extract_bvid_from_bilibili_urls():
    assert (
        extract_bvid("https://www.bilibili.com/video/BV1abcDEF234")
        == "BV1abcDEF234"
    )
    assert (
        extract_bvid("https://www.bilibili.com/video/BV1abcDEF234/?p=1")
        == "BV1abcDEF234"
    )


def test_extract_bvid_returns_none_for_missing_bvid():
    assert extract_bvid("https://www.bilibili.com/video/av123") is None


def test_fetch_json_uses_urllib_headers_timeout_and_parses_json(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def read(self) -> bytes:
            return b'{"ok": true, "count": 2}'

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(bilibili, "urlopen", fake_urlopen)

    result = bilibili.fetch_json(
        "https://api.example.com/subtitle.json",
        referer="https://www.bilibili.com/video/BV1abcDEF234",
    )

    assert result == {"ok": True, "count": 2}
    assert captured["timeout"] == 10
    assert captured["request"].full_url == "https://api.example.com/subtitle.json"
    assert captured["request"].has_header("User-agent")
    assert "Mozilla/5.0" in captured["request"].get_header("User-agent")
    assert (
        captured["request"].get_header("Referer")
        == "https://www.bilibili.com/video/BV1abcDEF234"
    )


def test_fetch_json_sets_cookie_header_when_cookie_provided(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def read(self) -> bytes:
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return FakeResponse()

    monkeypatch.setattr(bilibili, "urlopen", fake_urlopen)

    bilibili.fetch_json(
        "https://api.example.com/data",
        cookie="SESSDATA=abc123",
    )

    assert captured["request"].get_header("Cookie") == "SESSDATA=abc123"


def test_client_strips_cookie_line_breaks_before_request(monkeypatch):
    seen_cookies = []

    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        seen_cookies.append(cookie)
        if url.startswith("https://api.bilibili.com/x/player/pagelist"):
            return {"data": [{"cid": 456}]}
        if url.startswith("https://api.bilibili.com/x/player/v2"):
            return {
                "data": {
                    "subtitle": {
                        "subtitles": [
                            {"lan": "zh-Hans", "subtitle_url": "//subtitle.example.com/subtitle.json"}
                        ]
                    }
                }
            }
        if url == "https://subtitle.example.com/subtitle.json":
            return {"body": [{"from": 1.0, "content": "human subtitle"}]}
        raise AssertionError(f"unexpected URL: {url}")

    client = BilibiliSubtitleClient(
        fetch_json=fake_fetch_json,
        cookie="SESSDATA=abc;\n buvid3=def;\r\n",
    )

    assert client.fetch({"url": "https://www.bilibili.com/video/BV1abcDEF234"})
    assert seen_cookies[1] == "SESSDATA=abc; buvid3=def;"


def test_fetch_json_omits_cookie_header_when_cookie_not_provided(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def read(self) -> bytes:
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return FakeResponse()

    monkeypatch.setattr(bilibili, "urlopen", fake_urlopen)

    bilibili.fetch_json("https://api.example.com/data")

    assert not captured["request"].has_header("Cookie")


@pytest.mark.parametrize("cid", [456, "456"])
@pytest.mark.parametrize(
    ("subtitle_url", "expected_fetch_url"),
    [
        (
            "//subtitle.example.com/123456/subtitle.json",
            "https://subtitle.example.com/123456/subtitle.json",
        ),
        (
            "https://subtitle.example.com/123456/subtitle.json",
            "https://subtitle.example.com/123456/subtitle.json",
        ),
        (
            "http://subtitle.example.com/123456/subtitle.json",
            "http://subtitle.example.com/123456/subtitle.json",
        ),
        (
            "https://subtitle.example.com:443/123456/subtitle.json",
            "https://subtitle.example.com:443/123456/subtitle.json",
        ),
    ],
)
def test_fetch_subtitles_normalizes_body_entries(
    cid,
    subtitle_url,
    expected_fetch_url,
):
    calls = []

    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        calls.append((url, referer))
        if url.startswith("https://api.bilibili.com/x/player/pagelist"):
            return {"data": [{"cid": cid}]}
        if url.startswith("https://api.bilibili.com/x/player/v2"):
            return {
                "data": {
                    "subtitle": {
                        "subtitles": [{"subtitle_url": subtitle_url}]
                    }
                }
            }
        if url == expected_fetch_url:
            return {
                "body": [
                    {"from": 0, "content": "Zero line"},
                    {"from": 1, "content": " First line "},
                    {"from": "2.5", "content": "Second line"},
                    {"from": 3, "content": "   "},
                ]
            }
        raise AssertionError(f"unexpected URL: {url}")

    source_url = "https://www.bilibili.com/video/BV1abcDEF234/?p=1"
    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json)

    entries = client.fetch({"url": source_url})

    assert entries == [
        SubtitleEntry(start_seconds=0.0, text="Zero line"),
        SubtitleEntry(start_seconds=1.0, text="First line"),
        SubtitleEntry(start_seconds=2.5, text="Second line"),
    ]
    assert calls[0][0].endswith("/x/player/pagelist?bvid=BV1abcDEF234")
    assert calls[1][0].endswith("/x/player/v2?bvid=BV1abcDEF234&cid=456")
    assert calls[1][1] == source_url
    assert calls[2] == (expected_fetch_url, source_url)


def test_fetch_subtitles_returns_empty_when_player_has_no_subtitles():
    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        if url.startswith("https://api.bilibili.com/x/player/pagelist"):
            return {"data": [{"cid": 456}]}
        if url.startswith("https://api.bilibili.com/x/player/v2"):
            return {"data": {"subtitle": {"subtitles": []}}}
        raise AssertionError(f"unexpected URL: {url}")

    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json)

    assert client.fetch({"url": "https://www.bilibili.com/video/BV1abcDEF234"}) == []


def test_fetch_subtitles_returns_empty_when_first_subtitle_url_missing():
    calls = []

    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        calls.append((url, referer))
        if url.startswith("https://api.bilibili.com/x/player/pagelist"):
            return {"data": [{"cid": 456}]}
        if url.startswith("https://api.bilibili.com/x/player/v2"):
            return {"data": {"subtitle": {"subtitles": [{"subtitle_url": ""}]}}}
        raise AssertionError(f"unexpected subtitle body fetch: {url}")

    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json)

    assert client.fetch({"url": "https://www.bilibili.com/video/BV1abcDEF234"}) == []
    assert len(calls) == 2


def test_fetch_subtitles_prefers_human_track_and_skips_ai_prod_prefix_validation():
    calls = []
    human_url = (
        "https://aisubtitle.hdslb.com/bfs/ai_subtitle/prod/"
        "987654321456def456/subtitle.json"
    )
    ai_url = (
        "https://aisubtitle.hdslb.com/bfs/ai_subtitle/prod/"
        "123456789456abc123/subtitle.json"
    )

    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        calls.append((url, referer, cookie))
        if url.startswith("https://api.bilibili.com/x/player/pagelist"):
            return {"data": [{"cid": 456}]}
        if url.startswith("https://api.bilibili.com/x/player/v2"):
            return {
                "data": {
                    "aid": 123456789,
                    "subtitle": {
                        "subtitles": [
                            {"lan": "ai-zh", "subtitle_url": ai_url},
                            {"lan": "zh-Hans", "subtitle_url": human_url},
                        ]
                    },
                }
            }
        if url == human_url:
            return {"body": [{"from": 1.0, "content": "human subtitle"}]}
        raise AssertionError(f"unexpected URL: {url}")

    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json)

    entries = client.fetch({"url": "https://www.bilibili.com/video/BV1abcDEF234"})

    assert entries == [SubtitleEntry(start_seconds=1.0, text="human subtitle")]
    assert calls[-1][0] == human_url
    assert ai_url not in [call[0] for call in calls]


def test_fetch_subtitles_retries_until_player_returns_matching_prod_prefix():
    calls = []
    matched_url = (
        "https://aisubtitle.hdslb.com/bfs/ai_subtitle/prod/"
        "123456789456abc123/subtitle.json"
    )
    mismatched_url = (
        "https://aisubtitle.hdslb.com/bfs/ai_subtitle/prod/"
        "987654321456def456/subtitle.json"
    )
    player_responses = iter(
        [
            {
                "data": {
                    "aid": 123456789,
                    "subtitle": {
                        "subtitles": [{"lan": "ai-zh", "subtitle_url": mismatched_url}]
                    },
                }
            },
            {
                "data": {
                    "aid": 123456789,
                    "subtitle": {
                        "subtitles": [{"lan": "ai-zh", "subtitle_url": matched_url}]
                    },
                }
            },
        ]
    )

    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        calls.append((url, referer, cookie))
        if url.startswith("https://api.bilibili.com/x/player/pagelist"):
            return {"data": [{"cid": 456}]}
        if url.startswith("https://api.bilibili.com/x/player/v2"):
            return next(player_responses)
        if url == matched_url:
            return {"body": [{"from": 1.0, "content": "matched subtitle"}]}
        raise AssertionError(f"unexpected URL: {url}")

    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json)

    entries = client.fetch({"url": "https://www.bilibili.com/video/BV1abcDEF234"})

    assert entries == [SubtitleEntry(start_seconds=1.0, text="matched subtitle")]
    player_calls = [call for call in calls if "/x/player/v2" in call[0]]
    assert len(player_calls) == 2
    assert calls[-1][0] == matched_url


def test_fetch_subtitles_returns_empty_when_player_never_returns_matching_prod_prefix(
    monkeypatch,
):
    matched_prefix = "123456789456"
    calls = []
    mismatched_url = (
        "https://aisubtitle.hdslb.com/bfs/ai_subtitle/prod/"
        "987654321456def456/subtitle.json"
    )
    monotonic_values = iter([0, 0, 1, 2, 3, 4, 5, 6, 10])
    sleep_calls = []

    monkeypatch.setattr(bilibili.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(
        bilibili.time,
        "sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        calls.append((url, referer, cookie))
        if url.startswith("https://api.bilibili.com/x/player/pagelist"):
            return {"data": [{"cid": 456}]}
        if url.startswith("https://api.bilibili.com/x/player/v2"):
            return {
                "data": {
                    "aid": 123456789,
                    "subtitle": {
                        "subtitles": [
                            {
                                "lan": "ai-zh",
                                "subtitle_url": mismatched_url,
                            }
                        ]
                    },
                }
            }
        raise AssertionError(f"unexpected URL: {url}")

    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json)

    assert client.fetch({"url": "https://www.bilibili.com/video/BV1abcDEF234"}) == []
    player_calls = [call for call in calls if "/x/player/v2" in call[0]]
    body_calls = [call for call in calls if call[0] == mismatched_url]
    assert len(player_calls) > 5
    assert not body_calls
    assert sleep_calls == [
        bilibili.PLAYER_SUBTITLE_RETRY_INTERVAL_SECONDS
    ] * len(player_calls)
    assert matched_prefix not in mismatched_url


def _fetch_subtitles_with_player_response(player_response):
    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        if url.startswith("https://api.bilibili.com/x/player/pagelist"):
            return {"data": [{"cid": 456}]}
        if url.startswith("https://api.bilibili.com/x/player/v2"):
            return player_response
        raise AssertionError(f"unexpected URL: {url}")

    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json)

    return client.fetch({"url": "https://www.bilibili.com/video/BV1abcDEF234"})


@pytest.mark.parametrize(
    "player_response",
    [
        {"data": None},
        {"data": []},
        {"data": {"subtitle": []}},
        {"data": {"subtitle": {"subtitles": {}}}},
        {"data": {"subtitle": {"subtitles": [None]}}},
        {"data": {"subtitle": {"subtitles": [{"subtitle_url": 123}]}}},
    ],
)
def test_fetch_subtitles_raises_for_malformed_player_subtitles(player_response):
    with pytest.raises(BilibiliSubtitleError, match="player"):
        _fetch_subtitles_with_player_response(player_response)


@pytest.mark.parametrize(
    "subtitle_url",
    [
        "file:///tmp/subtitle.json",
        "ftp://subtitle.example.com/subtitle.json",
        "subtitle.example.com/subtitle.json",
        "http:///subtitle.json",
        "https:///subtitle.json",
        "http://example.com:abc/subtitle.json",
        "http://example.com:99999/subtitle.json",
    ],
)
def test_fetch_subtitles_raises_for_malformed_subtitle_url_without_fetching_body(
    subtitle_url,
):
    calls = []

    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        calls.append((url, referer))
        if url.startswith("https://api.bilibili.com/x/player/pagelist"):
            return {"data": [{"cid": 456}]}
        if url.startswith("https://api.bilibili.com/x/player/v2"):
            return {
                "data": {
                    "subtitle": {
                        "subtitles": [{"subtitle_url": subtitle_url}]
                    }
                }
            }
        raise AssertionError(f"unexpected subtitle body fetch: {url}")

    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json)

    with pytest.raises(
        BilibiliSubtitleError,
        match="Malformed Bilibili player response",
    ):
        client.fetch({"url": "https://www.bilibili.com/video/BV1abcDEF234"})

    assert len(calls) == 2


@pytest.mark.parametrize(
    "player_response",
    [
        {},
        {"data": {}},
        {"data": {"subtitle": {}}},
        {"data": {"subtitle": {"subtitles": [{"subtitle_url": ""}]}}},
    ],
)
def test_fetch_subtitles_returns_empty_for_missing_player_subtitles(player_response):
    assert _fetch_subtitles_with_player_response(player_response) == []


@pytest.mark.parametrize(
    "subtitle_body",
    [
        {"body": None},
        {"body": {}},
    ],
)
def test_fetch_subtitles_raises_for_malformed_subtitle_body(subtitle_body):
    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        if url.startswith("https://api.bilibili.com/x/player/pagelist"):
            return {"data": [{"cid": 456}]}
        if url.startswith("https://api.bilibili.com/x/player/v2"):
            return {
                "data": {
                    "subtitle": {
                        "subtitles": [
                            {"subtitle_url": "https://subtitle.example.com/subtitle.json"}
                        ]
                    }
                }
            }
        if url == "https://subtitle.example.com/subtitle.json":
            return subtitle_body
        raise AssertionError(f"unexpected URL: {url}")

    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json)

    with pytest.raises(BilibiliSubtitleError, match="subtitle body"):
        client.fetch({"url": "https://www.bilibili.com/video/BV1abcDEF234"})


@pytest.mark.parametrize(
    "body_item",
    [
        None,
        {"content": "Missing start"},
        {"from": True, "content": "x"},
        {"from": True, "content": "   "},
        {"from": "bad", "content": "x"},
        {"from": "nan", "content": "x"},
        {"from": "nan", "content": "   "},
        {"from": "inf", "content": "x"},
        {"from": -1, "content": "x"},
        {"from": [], "content": "x"},
        {"from": 1, "content": None},
    ],
)
def test_fetch_subtitles_raises_for_malformed_subtitle_body_items(body_item):
    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        if url.startswith("https://api.bilibili.com/x/player/pagelist"):
            return {"data": [{"cid": 456}]}
        if url.startswith("https://api.bilibili.com/x/player/v2"):
            return {
                "data": {
                    "subtitle": {
                        "subtitles": [
                            {"subtitle_url": "https://subtitle.example.com/subtitle.json"}
                        ]
                    }
                }
            }
        if url == "https://subtitle.example.com/subtitle.json":
            return {"body": [body_item]}
        raise AssertionError(f"unexpected URL: {url}")

    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json)

    with pytest.raises(BilibiliSubtitleError, match="subtitle body"):
        client.fetch({"url": "https://www.bilibili.com/video/BV1abcDEF234"})


def test_fetch_subtitles_returns_empty_when_subtitle_body_missing():
    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        if url.startswith("https://api.bilibili.com/x/player/pagelist"):
            return {"data": [{"cid": 456}]}
        if url.startswith("https://api.bilibili.com/x/player/v2"):
            return {
                "data": {
                    "subtitle": {
                        "subtitles": [
                            {"subtitle_url": "https://subtitle.example.com/subtitle.json"}
                        ]
                    }
                }
            }
        if url == "https://subtitle.example.com/subtitle.json":
            return {}
        raise AssertionError(f"unexpected URL: {url}")

    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json)

    assert client.fetch({"url": "https://www.bilibili.com/video/BV1abcDEF234"}) == []


def test_fetch_passes_cookie_to_player_v2():
    calls = []

    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        calls.append({"url": url, "referer": referer, "cookie": cookie})
        if "/x/player/pagelist" in url:
            return {"code": 0, "data": [{"cid": 456}]}
        if "/x/player/v2" in url:
            return {
                "code": 0,
                "data": {
                    "subtitle": {
                        "subtitles": [
                            {"subtitle_url": "//subtitle.example.com/subtitle.json"}
                        ]
                    }
                },
            }
        if "subtitle.example.com" in url:
            return {"body": [{"from": 1.0, "content": "test"}]}
        raise AssertionError(f"Unexpected URL: {url}")

    client = BilibiliSubtitleClient(
        fetch_json=fake_fetch_json,
        cookie="test_cookie_value",
    )
    entries = client.fetch({"url": "https://www.bilibili.com/video/BV1abcDEF234"})

    assert entries == [SubtitleEntry(start_seconds=1.0, text="test")]
    player_call = next(c for c in calls if "/x/player/v2" in c["url"])
    assert player_call["cookie"] == "test_cookie_value"


def test_fetch_subtitles_raises_for_missing_bvid():
    client = BilibiliSubtitleClient(fetch_json=lambda url, referer=None, cookie=None: {})

    with pytest.raises(BilibiliSubtitleError, match="BV id"):
        client.fetch({"url": "https://www.bilibili.com/video/av123"})


@pytest.mark.parametrize(
    "pagelist",
    [
        [],
        {},
        {"data": None},
        {"data": []},
        {"data": [None]},
    ],
)
def test_fetch_subtitles_raises_for_malformed_pagelist(pagelist):
    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        if url.startswith("https://api.bilibili.com/x/player/pagelist"):
            return pagelist
        raise AssertionError(f"unexpected URL: {url}")

    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json)

    with pytest.raises(BilibiliSubtitleError, match="pagelist"):
        client.fetch({"url": "https://www.bilibili.com/video/BV1abcDEF234"})


@pytest.mark.parametrize(
    "pagelist",
    [
        {"data": [{}]},
        {"data": [{"cid": None}]},
        {"data": [{"cid": ""}]},
        {"data": [{"cid": True}]},
        {"data": [{"cid": []}]},
        {"data": [{"cid": {}}]},
        {"data": [{"cid": 456.0}]},
        {"data": [{"cid": "456&x=y"}]},
        {"data": [{"cid": -1}]},
        {"data": [{"cid": "-1"}]},
    ],
)
def test_fetch_subtitles_raises_for_missing_cid(pagelist: dict):
    def fake_fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
        if url.startswith("https://api.bilibili.com/x/player/pagelist"):
            return pagelist
        raise AssertionError(f"unexpected URL: {url}")

    client = BilibiliSubtitleClient(fetch_json=fake_fetch_json)

    with pytest.raises(BilibiliSubtitleError, match="pagelist"):
        client.fetch({"url": "https://www.bilibili.com/video/BV1abcDEF234"})
