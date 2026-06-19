"""Schema migrations keyed off PRAGMA user_version."""

import logging

import aiosqlite

logger = logging.getLogger(__name__)


async def _migrate_documents_video_id_nullable(conn: aiosqlite.Connection) -> None:
    """Migration 1: make documents.video_id nullable with ON DELETE SET NULL.

    Rebuilds the documents table (SQLite cannot ALTER a column's NOT NULL or
    FK action in place). documents is only a child table, so dropping it does
    not violate any foreign keys.
    """
    await conn.executescript(
        """
        CREATE TABLE documents_new (
            id TEXT PRIMARY KEY,
            video_id TEXT,
            file_path TEXT NOT NULL,
            chunk_count INTEGER DEFAULT 0,
            is_indexed BOOLEAN DEFAULT 0,
            indexed_at TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE SET NULL
        );
        INSERT INTO documents_new (id, video_id, file_path, chunk_count, is_indexed, indexed_at)
        SELECT id, video_id, file_path, chunk_count, is_indexed, indexed_at FROM documents;
        DROP TABLE documents;
        ALTER TABLE documents_new RENAME TO documents;
        CREATE INDEX IF NOT EXISTS idx_documents_video_id ON documents(video_id);
        """
    )
    await conn.commit()


_MIGRATIONS = [_migrate_documents_video_id_nullable]


async def run_migrations(conn: aiosqlite.Connection) -> None:
    """Apply any pending migrations, tracked via PRAGMA user_version."""
    cursor = await conn.execute("PRAGMA user_version")
    row = await cursor.fetchone()
    current = row[0] if row else 0
    for index in range(current, len(_MIGRATIONS)):
        migration = _MIGRATIONS[index]
        logger.info("Applying migration %d: %s", index + 1, migration.__name__)
        await migration(conn)
        await conn.execute(f"PRAGMA user_version = {index + 1}")
        await conn.commit()
