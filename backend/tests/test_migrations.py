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
    status TEXT DEFAULT 'raw',
    indexed_at TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);
"""

# Schema at user_version 1 (post document-nullable migration, pre author_id
# migration).  Used to test the author_id addition migration in isolation.
SCHEMA_AT_V1 = """
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
    video_id TEXT,
    file_path TEXT NOT NULL,
    chunk_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'raw',
    indexed_at TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE SET NULL
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


async def _database_at_version_1(db_path: Path) -> None:
    """Create a database at user_version 1 (pre-author_id migration)."""
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(SCHEMA_AT_V1)
        await conn.execute("PRAGMA user_version = 1")
        await conn.execute(
            "INSERT INTO videos (id, platform, title, url) VALUES (?, ?, ?, ?)",
            ("v1", "bilibili", "t", "https://example.com"),
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_migration_adds_author_id(tmp_path: Path):
    """Migration 2: adds author_id TEXT column to videos table.

    Existing rows get NULL for the new column. The column sits after author
    and stores the platform-native author identifier (B站 owner.mid or
    抖音 sec_uid).
    """
    db_path = tmp_path / "metadata.db"
    await _database_at_version_1(db_path)

    async with aiosqlite.connect(db_path) as conn:
        await run_migrations(conn)

        # Column exists
        cursor = await conn.execute("PRAGMA table_info(videos)")
        rows = await cursor.fetchall()
        columns = [r[1] for r in rows]
        assert "author_id" in columns

        # Existing record has NULL author_id
        cursor = await conn.execute(
            "SELECT author_id FROM videos WHERE id = ?", ("v1",)
        )
        row = await cursor.fetchone()
        assert row[0] is None

        # PRAGMA user_version bumped to 2
        cursor = await conn.execute("PRAGMA user_version")
        row = await cursor.fetchone()
        assert row[0] == 5  # Now at migration 5 (latest)


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
