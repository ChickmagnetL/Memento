"""Tests for Markdown transcript draft writing."""

import pytest

from core.video.bilibili import SubtitleEntry
from core.video.markdown import MarkdownDraftWriter, format_timestamp


def test_format_timestamp_short_seconds():
    assert format_timestamp(1.2) == "[00:01]"
    assert format_timestamp(61.8) == "[01:01]"


def test_format_timestamp_includes_hours():
    assert format_timestamp(3661.0) == "[01:01:01]"


def test_writer_writes_exact_bilibili_draft_content_and_path(tmp_path):
    writer = MarkdownDraftWriter(tmp_path)
    video = {
        "id": "BV1abcDEF234",
        "title": "Example Video",
        "url": "https://www.bilibili.com/video/BV1abcDEF234",
    }
    entries = [
        SubtitleEntry(start_seconds=1.2, text="First line"),
        SubtitleEntry(start_seconds=5.9, text="Second line"),
    ]

    path = writer.write(video, entries)

    expected_path = tmp_path / "knowledge" / "bilibili" / "BV1abcDEF234.md"
    assert path == expected_path
    assert path.read_text(encoding="utf-8") == (
        "# Example Video\n"
        "\n"
        "- Platform: bilibili\n"
        "- Video ID: BV1abcDEF234\n"
        "- Source URL: https://www.bilibili.com/video/BV1abcDEF234\n"
        "\n"
        "## Transcript\n"
        "\n"
        "[00:01] First line\n"
        "[00:05] Second line\n"
    )


def test_writer_rejects_empty_entries(tmp_path):
    writer = MarkdownDraftWriter(tmp_path)

    with pytest.raises(ValueError, match="empty transcript"):
        writer.write(
            {
                "id": "BV1abcDEF234",
                "title": "Example Video",
                "url": "https://www.bilibili.com/video/BV1abcDEF234",
            },
            [],
        )
