"""Tests for schema migrations."""

from pathlib import Path

import aiosqlite
import pytest

from storage.migrations import run_migrations
from storage.sqlite_client import SQLiteClient


OLD_SCHEMA = """
CREATE TABLE videos (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    title TEXT NOT NULL,
    author TEXT,
    duration INTEGER,
    url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    chunk_count INTEGER DEFAULT 0,
    is_indexed BOOLEAN DEFAULT 0,
    indexed_at TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);
"""


async def _old_database(db_path: Path) -> None:
    """Create a database with the pre-migration schema and seed data."""
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(OLD_SCHEMA)
        await conn.execute(
            "INSERT INTO videos (id, platform, title, url) VALUES (?, ?, ?, ?)",
            ("v1", "bilibili", "t", "https://example.com"),
        )
        await conn.execute(
            "INSERT INTO documents (id, video_id, file_path) VALUES (?, ?, ?)",
            ("d1", "v1", "/tmp/d1.md"),
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_migration_makes_video_id_nullable_and_set_null(tmp_path: Path):
    db_path = tmp_path / "metadata.db"
    await _old_database(db_path)

    client = SQLiteClient(db_path)
    await client.connect()
    try:
        # video_id now nullable: can create a document with NULL video_id.
        doc = await client.create_document(
            document_id="d2", video_id=None, file_path="/tmp/d2.md"
        )
        assert doc["video_id"] is None

        # Deleting the video SET NULLs the child document instead of cascading.
        deleted = await client.delete_video("v1")
        assert deleted is True

        surviving = await client.get_document("d1")
        assert surviving is not None
        assert surviving["video_id"] is None
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_migration_is_idempotent(tmp_path: Path):
    client = SQLiteClient(tmp_path / "metadata.db")
    await client.connect()
    await client.close()

    client = SQLiteClient(tmp_path / "metadata.db")
    await client.connect()
    try:
        # user_version stays at target; re-connect does not error or duplicate.
        assert await client.create_document(
            document_id="d1", video_id=None, file_path="/tmp/d1.md"
        ) is not None
    finally:
        await client.close()
