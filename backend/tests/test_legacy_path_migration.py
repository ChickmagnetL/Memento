"""Tests for the one-off legacy knowledge path migration utility."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.documents.legacy_path_migration import (
    legacy_destination_path,
    migrate_legacy_knowledge_layout,
)


def _create_documents_db(db_path: Path, rows: list[tuple[str, str]]) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE documents (
                id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            "INSERT INTO documents (id, file_path) VALUES (?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def _list_document_paths(db_path: Path) -> dict[str, str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, file_path FROM documents ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    return {document_id: file_path for document_id, file_path in rows}


def test_legacy_destination_path_maps_raw_and_clean_variants(tmp_path: Path):
    platform_dir = tmp_path / "knowledge" / "bilibili"

    assert legacy_destination_path(platform_dir / "v1.md") == (
        platform_dir / "raw" / "v1.md"
    )
    assert legacy_destination_path(platform_dir / "v1.clean.md") == (
        platform_dir / "cleaned" / "v1.md"
    )
    assert legacy_destination_path(platform_dir / "v1.clean.clean.md") == (
        platform_dir / "cleaned" / "v1.md"
    )
    assert legacy_destination_path(platform_dir / "raw" / "v1.md") is None
    assert legacy_destination_path(platform_dir / "cleaned" / "v1.md") is None


def test_migration_defaults_to_dry_run_and_keeps_files_and_db_unchanged(
    tmp_path: Path,
):
    data_dir = tmp_path
    platform_dir = data_dir / "knowledge" / "bilibili"
    platform_dir.mkdir(parents=True)
    legacy_raw = platform_dir / "v1.md"
    legacy_clean = platform_dir / "v1.clean.clean.md"
    current_raw = platform_dir / "raw" / "v2.md"
    current_clean = platform_dir / "cleaned" / "v3.md"
    legacy_raw.write_text("raw", encoding="utf-8")
    legacy_clean.write_text("clean", encoding="utf-8")
    current_raw.parent.mkdir()
    current_raw.write_text("current raw", encoding="utf-8")
    current_clean.parent.mkdir()
    current_clean.write_text("current clean", encoding="utf-8")

    db_path = tmp_path / "metadata.db"
    _create_documents_db(
        db_path,
        [
            ("d1", str(legacy_raw)),
            ("d2", str(legacy_clean)),
            ("d3", str(current_raw)),
            ("d4", str(current_clean)),
        ],
    )

    result = migrate_legacy_knowledge_layout(data_dir=data_dir, db_path=db_path)

    assert result.applied is False
    assert {(move.source, move.destination) for move in result.plan.file_moves} == {
        (legacy_raw, platform_dir / "raw" / "v1.md"),
        (legacy_clean, platform_dir / "cleaned" / "v1.md"),
    }
    assert {
        (update.document_id, update.old_path, update.new_path)
        for update in result.plan.document_updates
    } == {
        ("d1", str(legacy_raw), str(platform_dir / "raw" / "v1.md")),
        ("d2", str(legacy_clean), str(platform_dir / "cleaned" / "v1.md")),
    }
    assert legacy_raw.exists()
    assert legacy_clean.exists()
    assert not (platform_dir / "raw" / "v1.md").exists()
    assert not (platform_dir / "cleaned" / "v1.md").exists()
    assert _list_document_paths(db_path) == {
        "d1": str(legacy_raw),
        "d2": str(legacy_clean),
        "d3": str(current_raw),
        "d4": str(current_clean),
    }


def test_migration_apply_moves_files_and_updates_matching_document_rows(
    tmp_path: Path,
):
    data_dir = tmp_path
    platform_dir = data_dir / "knowledge" / "bilibili"
    platform_dir.mkdir(parents=True)
    legacy_raw = platform_dir / "v1.md"
    legacy_clean = platform_dir / "v1.clean.md"
    legacy_raw.write_text("raw", encoding="utf-8")
    legacy_clean.write_text("clean", encoding="utf-8")

    db_path = tmp_path / "metadata.db"
    _create_documents_db(
        db_path,
        [
            ("d1", str(legacy_raw)),
            ("d2", str(legacy_clean)),
            ("d3", str(platform_dir / "raw" / "already.md")),
        ],
    )

    result = migrate_legacy_knowledge_layout(
        data_dir=data_dir,
        db_path=db_path,
        apply=True,
    )

    assert result.applied is True
    assert result.moved_file_count == 2
    assert result.updated_row_count == 2
    assert not legacy_raw.exists()
    assert not legacy_clean.exists()
    assert (platform_dir / "raw" / "v1.md").read_text(encoding="utf-8") == "raw"
    assert (platform_dir / "cleaned" / "v1.md").read_text(encoding="utf-8") == "clean"
    assert _list_document_paths(db_path) == {
        "d1": str(platform_dir / "raw" / "v1.md"),
        "d2": str(platform_dir / "cleaned" / "v1.md"),
        "d3": str(platform_dir / "raw" / "already.md"),
    }


def test_migration_plan_reports_duplicate_destination_conflicts_and_apply_fails(
    tmp_path: Path,
):
    data_dir = tmp_path
    platform_dir = data_dir / "knowledge" / "bilibili"
    platform_dir.mkdir(parents=True)
    first_legacy = platform_dir / "v1.clean.md"
    second_legacy = platform_dir / "v1.clean.clean.md"
    first_legacy.write_text("first", encoding="utf-8")
    second_legacy.write_text("second", encoding="utf-8")

    db_path = tmp_path / "metadata.db"
    _create_documents_db(
        db_path,
        [
            ("d1", str(first_legacy)),
            ("d2", str(second_legacy)),
        ],
    )

    dry_run = migrate_legacy_knowledge_layout(data_dir=data_dir, db_path=db_path)

    assert dry_run.applied is False
    assert len(dry_run.plan.conflicts) == 1
    conflict = dry_run.plan.conflicts[0]
    assert conflict.reason == "duplicate_destination"
    assert conflict.destination == platform_dir / "cleaned" / "v1.md"
    assert set(conflict.sources) == {first_legacy, second_legacy}

    try:
        migrate_legacy_knowledge_layout(data_dir=data_dir, db_path=db_path, apply=True)
    except ValueError as exc:
        assert "duplicate_destination" in str(exc)
        assert str(platform_dir / "cleaned" / "v1.md") in str(exc)
    else:
        raise AssertionError("apply=True should fail when duplicate destinations exist")

    assert first_legacy.exists()
    assert second_legacy.exists()
    assert not (platform_dir / "cleaned" / "v1.md").exists()
    assert _list_document_paths(db_path) == {
        "d1": str(first_legacy),
        "d2": str(second_legacy),
    }


def test_migration_plan_reports_existing_destination_conflicts_and_apply_fails(
    tmp_path: Path,
):
    data_dir = tmp_path
    platform_dir = data_dir / "knowledge" / "bilibili"
    platform_dir.mkdir(parents=True)
    legacy_clean = platform_dir / "v1.clean.md"
    existing_destination = platform_dir / "cleaned" / "v1.md"
    legacy_clean.write_text("legacy", encoding="utf-8")
    existing_destination.parent.mkdir(parents=True)
    existing_destination.write_text("current", encoding="utf-8")

    db_path = tmp_path / "metadata.db"
    _create_documents_db(db_path, [("d1", str(legacy_clean))])

    dry_run = migrate_legacy_knowledge_layout(data_dir=data_dir, db_path=db_path)

    assert dry_run.applied is False
    assert len(dry_run.plan.conflicts) == 1
    conflict = dry_run.plan.conflicts[0]
    assert conflict.reason == "destination_exists"
    assert conflict.destination == existing_destination
    assert conflict.sources == (legacy_clean,)

    try:
        migrate_legacy_knowledge_layout(data_dir=data_dir, db_path=db_path, apply=True)
    except ValueError as exc:
        assert "destination_exists" in str(exc)
        assert str(existing_destination) in str(exc)
    else:
        raise AssertionError("apply=True should fail when destination already exists")

    assert legacy_clean.exists()
    assert existing_destination.read_text(encoding="utf-8") == "current"
    assert _list_document_paths(db_path) == {"d1": str(legacy_clean)}
