"""Tests for canonical knowledge document paths."""

from pathlib import Path

from core.documents.paths import (
    cleaned_document_path_for_source,
    is_raw_document_path,
    preferred_clean_source_path,
    raw_document_path,
)


def test_raw_document_path_uses_platform_raw_directory(tmp_path: Path):
    assert raw_document_path(tmp_path, "bilibili", "v1") == (
        tmp_path / "knowledge" / "bilibili" / "raw" / "v1.md"
    )


def test_cleaned_document_path_for_raw_source_uses_cleaned_directory(
    tmp_path: Path,
):
    source = tmp_path / "knowledge" / "bilibili" / "raw" / "v1.md"

    assert cleaned_document_path_for_source(source) == (
        tmp_path / "knowledge" / "bilibili" / "cleaned" / "v1.md"
    )


def test_cleaned_document_path_for_cleaned_source_does_not_stack_clean_suffix(
    tmp_path: Path,
):
    source = tmp_path / "knowledge" / "bilibili" / "cleaned" / "v1.md"

    assert cleaned_document_path_for_source(source) == source
    assert cleaned_document_path_for_source(source).name == "v1.md"


def test_cleaned_document_path_prefers_video_id_when_source_has_clean_suffix(
    tmp_path: Path,
):
    source = tmp_path / "knowledge" / "bilibili" / "v1.clean.md"

    assert cleaned_document_path_for_source(source, video_id="v1") == (
        tmp_path / "knowledge" / "bilibili" / "cleaned" / "v1.md"
    )


def test_cleaned_document_path_collapses_repeated_clean_suffixes(tmp_path: Path):
    source = tmp_path / "knowledge" / "bilibili" / "v1.clean.clean.md"

    assert cleaned_document_path_for_source(source) == (
        tmp_path / "knowledge" / "bilibili" / "cleaned" / "v1.md"
    )


def test_preferred_clean_source_path_uses_sibling_raw_file_for_cleaned_source(
    tmp_path: Path,
):
    raw = tmp_path / "knowledge" / "bilibili" / "raw" / "v1.md"
    raw.parent.mkdir(parents=True)
    raw.write_text("raw", encoding="utf-8")
    cleaned = tmp_path / "knowledge" / "bilibili" / "cleaned" / "v1.md"

    assert preferred_clean_source_path(cleaned) == raw


def test_preferred_clean_source_path_uses_legacy_raw_file_for_clean_suffix(
    tmp_path: Path,
):
    raw = tmp_path / "knowledge" / "bilibili" / "v1.md"
    raw.parent.mkdir(parents=True)
    raw.write_text("raw", encoding="utf-8")
    cleaned = tmp_path / "knowledge" / "bilibili" / "v1.clean.md"

    assert preferred_clean_source_path(cleaned) == raw


def test_preferred_clean_source_path_prefers_canonical_raw_file_for_legacy_clean_suffix(
    tmp_path: Path,
):
    canonical_raw = tmp_path / "knowledge" / "bilibili" / "raw" / "v1.md"
    canonical_raw.parent.mkdir(parents=True)
    canonical_raw.write_text("raw", encoding="utf-8")
    legacy_raw = tmp_path / "knowledge" / "bilibili" / "v1.md"
    legacy_raw.write_text("legacy raw", encoding="utf-8")

    assert preferred_clean_source_path(
        tmp_path / "knowledge" / "bilibili" / "v1.clean.md"
    ) == canonical_raw
    assert preferred_clean_source_path(
        tmp_path / "knowledge" / "bilibili" / "v1.clean.clean.md"
    ) == canonical_raw


def test_is_raw_document_path_matches_only_raw_markdown_paths(tmp_path: Path):
    raw = tmp_path / "knowledge" / "bilibili" / "raw" / "v1.md"
    cleaned = tmp_path / "knowledge" / "bilibili" / "cleaned" / "v1.md"
    nested = tmp_path / "knowledge" / "bilibili" / "raw" / "nested" / "v1.md"

    assert is_raw_document_path(raw) is True
    assert is_raw_document_path(cleaned) is False
    assert is_raw_document_path(nested) is False
