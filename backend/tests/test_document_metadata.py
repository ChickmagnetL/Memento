"""Tests for markdown header metadata parsing."""

from pathlib import Path

from core.documents.metadata import parse_markdown_metadata


def test_parse_markdown_metadata_reads_header(tmp_path: Path):
    path = tmp_path / "v1.md"
    path.write_text(
        "# 示例视频\n"
        "\n"
        "- Platform: bilibili\n"
        "- Video ID: abc123\n"
        "- Source URL: https://www.bilibili.com/video/BV1xx\n"
        "\n"
        "## Transcript\n"
        "\n"
        "[00:01] 内容\n",
        encoding="utf-8",
    )

    meta = parse_markdown_metadata(path)

    assert meta == {
        "title": "示例视频",
        "platform": "bilibili",
        "source_url": "https://www.bilibili.com/video/BV1xx",
        "video_id": "abc123",
        "author": None,
    }


def test_parse_markdown_metadata_missing_fields_are_none(tmp_path: Path):
    path = tmp_path / "partial.md"
    path.write_text("# 只有标题\n\n正文无元数据\n", encoding="utf-8")

    meta = parse_markdown_metadata(path)

    assert meta["title"] == "只有标题"
    assert meta["platform"] is None
    assert meta["source_url"] is None
    assert meta["video_id"] is None
    assert meta["author"] is None


def test_parse_markdown_metadata_reads_author(tmp_path: Path):
    path = tmp_path / "with_author.md"
    path.write_text(
        "# 示例视频\n"
        "\n"
        "- Platform: bilibili\n"
        "- Video ID: abc123\n"
        "- Source URL: https://www.bilibili.com/video/BV1xx\n"
        "- Author: 测试作者\n"
        "\n"
        "## Transcript\n",
        encoding="utf-8",
    )

    meta = parse_markdown_metadata(path)

    assert meta["title"] == "示例视频"
    assert meta["author"] == "测试作者"


def test_parse_markdown_metadata_unreadable_file_returns_nones(tmp_path: Path):
    meta = parse_markdown_metadata(tmp_path / "missing.md")

    assert meta == {
        "title": None,
        "platform": None,
        "source_url": None,
        "video_id": None,
        "author": None,
    }
