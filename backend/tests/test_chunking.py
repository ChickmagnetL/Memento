"""Tests for markdown document chunking."""

import pytest

from core.rag.chunking import Chunk, chunk_markdown

SAMPLE_DRAFT = """# 示例视频

- Platform: bilibili
- Video ID: video-1
- Source URL: https://www.bilibili.com/video/BV1abc

## Transcript

[00:01] 第一行内容
[00:05] 第二行内容
"""


def test_small_draft_yields_single_chunk_with_metadata():
    chunks = chunk_markdown(
        SAMPLE_DRAFT,
        video_id="video-1",
        document_id="doc-1",
        chunk_size=800,
        overlap=80,
    )

    assert len(chunks) == 1
    chunk = chunks[0]
    assert isinstance(chunk, Chunk)
    assert chunk.video_id == "video-1"
    assert chunk.document_id == "doc-1"
    assert chunk.chunk_index == 0
    assert chunk.title_path == "示例视频 > Transcript"
    assert chunk.text.startswith("示例视频 > Transcript\n\n")
    assert "[00:01] 第一行内容" in chunk.text
    assert "[00:05] 第二行内容" in chunk.text


def test_empty_content_raises_value_error():
    with pytest.raises(ValueError):
        chunk_markdown("", video_id="v", document_id="d", chunk_size=800, overlap=80)


def _make_long_draft(line_count: int) -> str:
    lines = "\n".join(
        f"[{i // 60:02d}:{i % 60:02d}] 这是第{i}行的转录内容，用于撑长度。"
        for i in range(line_count)
    )
    return f"# 长视频\n\n## Transcript\n\n{lines}\n"


def test_long_section_splits_into_multiple_chunks_within_size():
    draft = _make_long_draft(80)
    chunks = chunk_markdown(
        draft, video_id="v", document_id="d", chunk_size=400, overlap=40
    )

    assert len(chunks) > 1
    for chunk in chunks:
        # Body must respect chunk_size; title path prefix is extra.
        body = chunk.text.split("\n\n", 1)[1]
        assert len(body) <= 400 + 40  # packed body + prepended overlap
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_adjacent_chunks_share_overlap_text():
    draft = _make_long_draft(80)
    chunks = chunk_markdown(
        draft, video_id="v", document_id="d", chunk_size=400, overlap=40
    )

    first_body = chunks[0].text.split("\n\n", 1)[1]
    second_body = chunks[1].text.split("\n\n", 1)[1]
    overlap_text = first_body[-40:]
    assert second_body.startswith(overlap_text)


def test_every_chunk_keeps_title_path_prefix():
    draft = _make_long_draft(80)
    chunks = chunk_markdown(
        draft, video_id="v", document_id="d", chunk_size=400, overlap=40
    )

    for chunk in chunks:
        assert chunk.title_path == "长视频 > Transcript"
        assert chunk.text.startswith("长视频 > Transcript\n\n")


def test_start_timestamp_extracted_per_chunk():
    draft = _make_long_draft(80)
    chunks = chunk_markdown(
        draft, video_id="v", document_id="d", chunk_size=400, overlap=0
    )

    # With zero overlap each chunk starts at its own first subtitle line.
    assert chunks[0].start_timestamp == "00:00"
    assert chunks[1].start_timestamp is not None
    assert chunks[1].start_timestamp != "00:00"


def test_hour_level_timestamp_supported():
    draft = "# 长视频\n\n## Transcript\n\n[01:02:03] 一小时后的内容\n"
    chunks = chunk_markdown(
        draft, video_id="v", document_id="d", chunk_size=800, overlap=80
    )
    assert chunks[0].start_timestamp == "01:02:03"


def test_section_without_timestamp_has_none():
    draft = "# 视频\n\n## Summary\n\n这一段没有时间戳。\n"
    chunks = chunk_markdown(
        draft, video_id="v", document_id="d", chunk_size=800, overlap=80
    )
    assert chunks[0].start_timestamp is None