"""Tests for YouTube URL, metadata, and subtitle helpers."""

import json

import pytest

from core.video.bilibili import (
    REASON_NON_CHINESE_SUBTITLES,
    REASON_NO_SUBTITLES,
    REASON_OK,
)
from core.video import youtube
from core.video.youtube import YouTubeError, YouTubeSubtitleClient, extract_video_id


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123",
        "https://youtu.be/dQw4w9WgXcQ?t=42",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
    ],
)
def test_extract_video_id_accepts_supported_single_video_urls(url: str):
    assert extract_video_id(url) == "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/playlist?list=PL123",
        "https://www.youtube.com/channel/UC123",
        "https://www.youtube.com/live/dQw4w9WgXcQ",
        "https://youtube.example.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/not-an-id",
    ],
)
def test_extract_video_id_rejects_unsupported_youtube_urls(url: str):
    assert extract_video_id(url) is None


def test_extract_info_probes_without_download_or_playlist(monkeypatch):
    seen = {}

    class FakeYoutubeDL:
        def __init__(self, options):
            seen["options"] = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def extract_info(self, url: str, *, download: bool):
            seen["call"] = (url, download)
            return {"id": "dQw4w9WgXcQ"}

    monkeypatch.setattr(youtube.yt_dlp, "YoutubeDL", FakeYoutubeDL)

    result = youtube.extract_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert result == {"id": "dQw4w9WgXcQ"}
    assert seen["call"] == (
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        False,
    )
    assert seen["options"]["skip_download"] is True
    assert seen["options"]["noplaylist"] is True


def test_fetch_metadata_uses_channel_fields_and_integer_duration():
    client = YouTubeSubtitleClient(
        info_extractor=lambda url: {
            "id": "dQw4w9WgXcQ",
            "title": "Video title",
            "channel": "Channel name",
            "channel_id": "UC-stable-id",
            "uploader": "Uploader fallback",
            "uploader_id": "@fallback",
            "duration": 123.8,
        }
    )

    assert client.fetch_metadata("https://youtu.be/dQw4w9WgXcQ") == {
        "id": "dQw4w9WgXcQ",
        "title": "Video title",
        "author": "Channel name",
        "author_id": "UC-stable-id",
        "duration": 123,
    }


def test_fetch_metadata_rejects_incomplete_probe():
    client = YouTubeSubtitleClient(
        info_extractor=lambda url: {
            "id": "dQw4w9WgXcQ",
            "title": "Missing channel metadata",
            "duration": 12,
        }
    )

    with pytest.raises(YouTubeError, match="incomplete"):
        client.fetch_metadata("https://youtu.be/dQw4w9WgXcQ")


def _json3(*events: tuple[int, str]) -> bytes:
    return json.dumps(
        {
            "events": [
                {"tStartMs": start, "segs": [{"utf8": text}]} for start, text in events
            ]
        }
    ).encode()


def test_creator_subtitles_are_preferred_over_automatic_captions():
    fetched_urls = []
    client = YouTubeSubtitleClient(
        info_extractor=lambda url: {
            "subtitles": {
                "zh-Hans": [{"ext": "json3", "url": "https://captions.test/creator"}]
            },
            "automatic_captions": {
                "zh-Hans": [{"ext": "json3", "url": "https://captions.test/automatic"}]
            },
        },
        content_fetcher=lambda url, headers: (
            fetched_urls.append(url) or _json3((1250, "创作者字幕"))
        ),
    )

    outcome = client.fetch_outcome({"url": "https://youtu.be/dQw4w9WgXcQ"})

    assert outcome.reason == REASON_OK
    assert [(entry.start_seconds, entry.text) for entry in outcome.entries] == [
        (1.25, "创作者字幕")
    ]
    assert fetched_urls == ["https://captions.test/creator"]


def test_chinese_automatic_caption_is_preferred_over_english_creator_subtitle():
    fetched_urls = []
    client = YouTubeSubtitleClient(
        info_extractor=lambda url: {
            "subtitles": {"en": [{"ext": "json3", "url": "https://captions.test/en"}]},
            "automatic_captions": {
                "zh-Hans": [{"ext": "json3", "url": "https://captions.test/zh-auto"}]
            },
        },
        content_fetcher=lambda url, headers: (
            fetched_urls.append(url) or _json3((1250, "中文自动字幕"))
        ),
    )

    outcome = client.fetch_outcome({"url": "https://youtu.be/dQw4w9WgXcQ"})

    assert outcome.reason == REASON_OK
    assert [entry.text for entry in outcome.entries] == ["中文自动字幕"]
    assert fetched_urls == ["https://captions.test/zh-auto"]


def test_automatic_caption_fallback_filters_live_chat():
    client = YouTubeSubtitleClient(
        info_extractor=lambda url: {
            "subtitles": {"live_chat": [{"ext": "json3", "url": "https://chat"}]},
            "automatic_captions": {
                "zh-CN": [{"ext": "json3", "url": "https://captions.test/automatic"}]
            },
        },
        content_fetcher=lambda url, headers: _json3((0, "自动字幕")),
    )

    outcome = client.fetch_outcome({"url": "https://youtu.be/dQw4w9WgXcQ"})

    assert outcome.reason == REASON_OK
    assert [entry.text for entry in outcome.entries] == ["自动字幕"]


def test_non_chinese_subtitles_report_languages_then_allow_import():
    info = {
        "language": "ja",
        "subtitles": {
            "en": [{"ext": "json3", "url": "https://captions.test/en"}],
            "ja": [{"ext": "json3", "url": "https://captions.test/ja"}],
            "live_chat": [{"ext": "json3", "url": "https://chat"}],
        },
    }
    fetched_urls = []
    client = YouTubeSubtitleClient(
        info_extractor=lambda url: info,
        content_fetcher=lambda url, headers: (
            fetched_urls.append(url) or _json3((500, "日本語"))
        ),
    )
    video = {"url": "https://youtu.be/dQw4w9WgXcQ"}

    blocked = client.fetch_outcome(video)
    allowed = client.fetch_outcome(video, allow_non_chinese=True)

    assert blocked.reason == REASON_NON_CHINESE_SUBTITLES
    assert blocked.available_languages == ("en", "ja")
    assert allowed.reason == REASON_OK
    assert [entry.text for entry in allowed.entries] == ["日本語"]
    assert fetched_urls == ["https://captions.test/ja"]


def test_translated_automatic_captions_are_not_reported_as_source_languages():
    fetched_urls = []
    client = YouTubeSubtitleClient(
        info_extractor=lambda url: {
            "language": "en-US",
            "automatic_captions": {
                "zh-Hans": [
                    {
                        "ext": "json3",
                        "url": (
                            "https://captions.test/captions?lang=en&kind=asr"
                            "&tlang=zh-Hans"
                        ),
                    }
                ],
                "en-orig": [
                    {
                        "ext": "json3",
                        "url": "https://captions.test/captions?lang=en&kind=asr",
                    }
                ],
                "en": [
                    {
                        "ext": "json3",
                        "url": "https://captions.test/captions?lang=en&kind=asr",
                    }
                ],
            },
        },
        content_fetcher=lambda url, headers: fetched_urls.append(url) or b"",
    )

    outcome = client.fetch_outcome({"url": "https://youtu.be/dQw4w9WgXcQ"})

    assert outcome.reason == REASON_NON_CHINESE_SUBTITLES
    assert outcome.available_languages == ("en",)
    assert fetched_urls == []


def test_failed_chinese_track_offers_working_non_chinese_track():
    fetched_urls = []

    def fetch(url, headers):
        fetched_urls.append(url)
        if url.endswith("/zh"):
            raise OSError("HTTP 429")
        return _json3((500, "English"))

    client = YouTubeSubtitleClient(
        info_extractor=lambda url: {
            "subtitles": {
                "zh-Hans": [{"ext": "json3", "url": "https://captions.test/zh"}],
                "en": [{"ext": "json3", "url": "https://captions.test/en"}],
            }
        },
        content_fetcher=fetch,
    )
    video = {"url": "https://youtu.be/dQw4w9WgXcQ"}

    blocked = client.fetch_outcome(video)
    allowed = client.fetch_outcome(video, allow_non_chinese=True)

    assert blocked.reason == REASON_NON_CHINESE_SUBTITLES
    assert blocked.available_languages == ("en",)
    assert allowed.reason == REASON_OK
    assert [entry.text for entry in allowed.entries] == ["English"]
    assert fetched_urls == [
        "https://captions.test/zh",
        "https://captions.test/zh",
        "https://captions.test/en",
    ]


def test_no_usable_subtitles_returns_asr_eligible_outcome():
    client = YouTubeSubtitleClient(
        info_extractor=lambda url: {
            "subtitles": {"live_chat": [{"ext": "json3", "url": "https://chat"}]},
            "automatic_captions": {},
        }
    )

    outcome = client.fetch_outcome({"url": "https://youtu.be/dQw4w9WgXcQ"})

    assert outcome.reason == REASON_NO_SUBTITLES
    assert outcome.has_subtitles is False


def test_vtt_subtitles_are_converted_to_timestamped_entries():
    vtt = b"""WEBVTT

00:00:02.500 --> 00:00:04.000
Hello <b>world</b>
"""
    client = YouTubeSubtitleClient(
        info_extractor=lambda url: {
            "subtitles": {"zh": [{"ext": "vtt", "url": "https://captions.test/vtt"}]}
        },
        content_fetcher=lambda url, headers: vtt,
    )

    outcome = client.fetch_outcome({"url": "https://youtu.be/dQw4w9WgXcQ"})

    assert outcome.reason == REASON_OK
    assert [(entry.start_seconds, entry.text) for entry in outcome.entries] == [
        (2.5, "Hello world")
    ]


def test_vtt_format_is_used_when_json3_fetch_fails():
    fetched_urls = []
    vtt = b"""WEBVTT

00:00:03.000 --> 00:00:04.000
Format fallback
"""

    def fetch(url, headers):
        fetched_urls.append(url)
        if url.endswith("/json3"):
            raise OSError("JSON3 unavailable")
        return vtt

    client = YouTubeSubtitleClient(
        info_extractor=lambda url: {
            "subtitles": {
                "zh": [
                    {"ext": "json3", "url": "https://captions.test/json3"},
                    {"ext": "vtt", "url": "https://captions.test/vtt"},
                ]
            }
        },
        content_fetcher=fetch,
    )

    outcome = client.fetch_outcome({"url": "https://youtu.be/dQw4w9WgXcQ"})

    assert outcome.reason == REASON_OK
    assert [entry.text for entry in outcome.entries] == ["Format fallback"]
    assert fetched_urls == [
        "https://captions.test/json3",
        "https://captions.test/vtt",
    ]
