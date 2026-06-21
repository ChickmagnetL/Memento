"""Tests for Douyin metadata resolution."""

import json

import pytest

from core.video.douyin import DouyinError, DouyinMetadata, _build_http_resolver


def _stub_fetcher_response(monkeypatch, body: bytes) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def read(self) -> bytes:
            return body

    monkeypatch.setattr(
        "core.video.douyin.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(),
    )


def test_http_resolver_returns_video_url_and_metadata(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def read(self) -> bytes:
            return (
                b'{"video_url":"https://cdn.example.com/video.mp4",'
                b'"title":"Example",'
                b'"author":"Creator",'
                b'"author_id":"sec-user",'
                b'"duration":42}'
            )

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("core.video.douyin.urllib.request.urlopen", fake_urlopen)

    resolve = _build_http_resolver("http://fetcher.local")

    assert resolve("1234567890", "cookie=value") == DouyinMetadata(
        video_url="https://cdn.example.com/video.mp4",
        title="Example",
        author="Creator",
        author_id="sec-user",
        duration=42,
    )
    assert captured == {
        "url": "http://fetcher.local/resolve",
        "timeout": 30,
    }


def test_http_resolver_defaults_missing_metadata_to_none(monkeypatch):
    _stub_fetcher_response(
        monkeypatch,
        b'{"video_url":"https://cdn.example.com/video.mp4"}',
    )

    resolve = _build_http_resolver("http://fetcher.local")

    assert resolve("1234567890", "") == DouyinMetadata(
        video_url="https://cdn.example.com/video.mp4",
        title=None,
        author=None,
        author_id=None,
        duration=None,
    )


def test_http_resolver_rejects_non_dict_response(monkeypatch):
    _stub_fetcher_response(monkeypatch, b'["not", "an", "object"]')
    resolve = _build_http_resolver("http://fetcher.local")

    with pytest.raises(DouyinError, match="Fetcher returned no video URL"):
        resolve("1234567890", "")


@pytest.mark.parametrize("video_url", ["", 123, True, None])
def test_http_resolver_rejects_invalid_video_url(monkeypatch, video_url):
    _stub_fetcher_response(
        monkeypatch,
        json.dumps({"video_url": video_url}).encode(),
    )
    resolve = _build_http_resolver("http://fetcher.local")

    with pytest.raises(DouyinError, match="Fetcher returned no video URL"):
        resolve("1234567890", "")


def test_http_resolver_normalizes_malformed_metadata_to_none(monkeypatch):
    _stub_fetcher_response(
        monkeypatch,
        (
            b'{"video_url":"https://cdn.example.com/video.mp4",'
            b'"title":["not","a","string"],'
            b'"author":123,'
            b'"author_id":true,'
            b'"duration":false}'
        ),
    )
    resolve = _build_http_resolver("http://fetcher.local")

    assert resolve("1234567890", "") == DouyinMetadata(
        video_url="https://cdn.example.com/video.mp4",
        title=None,
        author=None,
        author_id=None,
        duration=None,
    )


def test_downloader_uses_resolved_video_url_for_download(tmp_path):
    from core.video.douyin import DouyinAudioDownloader

    downloaded = []

    downloader = DouyinAudioDownloader(
        data_dir=tmp_path,
        keep_videos=False,
        cookie="cookie=value",
        resolve_video_url=lambda aweme_id, cookie: DouyinMetadata(
            video_url="https://cdn.example.com/video.mp4",
            title="Example",
            author="Creator",
            author_id="sec-user",
            duration=42,
        ),
        fetch_bytes=lambda url: downloaded.append(url) or b"MP4DATA",
        run_command=lambda args: __import__("pathlib").Path(args[-1]).write_bytes(b"RIFF"),
    )

    wav_path = downloader.download(
        {
            "id": "video-1",
            "platform": "douyin",
            "title": "Example",
            "url": "https://www.douyin.com/video/1234567890",
            "status": "processing",
        }
    )

    assert wav_path.exists()
    assert downloaded == ["https://cdn.example.com/video.mp4"]
