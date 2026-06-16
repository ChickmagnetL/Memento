"""
SQLite database client for Memento metadata storage.

Phase 1 scope: Initialize database connection and create tables from schema.
CRUD operations are added in Phase 2 when video processing is implemented.

Author: Memento Team
Last Updated: 2026-06-07
"""

import aiosqlite
from pathlib import Path


class SQLiteClient:
    """
    Async SQLite client for Memento metadata.

    Phase 1: Connect, initialize schema, close.
    Phase 2+: Add CRUD operations as needed.

    Attributes:
        db_path (Path): Path to SQLite database file
        _conn (aiosqlite.Connection): Database connection
    """

    def __init__(self, db_path: Path | str):
        """
        Initialize SQLite client.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """
        Connect to database and initialize schema.

        Creates the database file if it doesn't exist.
        Executes schema.sql to create tables and indexes.
        """
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Open connection
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")

        # Load and execute schema
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path) as f:
            schema = f.read()

        await self._conn.executescript(schema)
        await self._conn.commit()

    def _require_conn(self) -> aiosqlite.Connection:
        """Return an active connection or raise a clear error."""
        if self._conn is None:
            raise RuntimeError("SQLiteClient is not connected")
        return self._conn

    @staticmethod
    def _row_to_dict(row: aiosqlite.Row) -> dict:
        """Convert a SQLite row to a plain dict."""
        return dict(row)

    async def create_video(
        self,
        *,
        video_id: str,
        platform: str,
        title: str,
        url: str,
        author: str | None = None,
        duration: int | None = None,
    ) -> dict:
        """Create a pending video record and return it."""
        conn = self._require_conn()
        await conn.execute(
            """
            INSERT INTO videos (id, platform, title, author, duration, url, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """,
            (video_id, platform, title, author, duration, url),
        )
        await conn.commit()

        video = await self.get_video(video_id)
        if video is None:
            raise RuntimeError("Created video could not be loaded")
        return video

    async def list_videos(self) -> list[dict]:
        """List video records with newest records first."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT id, platform, title, author, duration, url, status, error_message, created_at, processed_at
            FROM videos
            ORDER BY created_at DESC, id DESC
            """
        )
        rows = await cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    async def get_video(self, video_id: str) -> dict | None:
        """Return a video record by ID, or None when missing."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT id, platform, title, author, duration, url, status, error_message, created_at, processed_at
            FROM videos
            WHERE id = ?
            """,
            (video_id,),
        )
        row = await cursor.fetchone()
        return self._row_to_dict(row) if row else None

    async def update_video_status(self, video_id: str, status: str, error_message: str | None = None) -> dict | None:
        """Update a video status and return the updated record."""
        conn = self._require_conn()
        processed_at_sql = (
            ", processed_at = CURRENT_TIMESTAMP" if status in {"completed", "failed"} else ""
        )
        await conn.execute(
            f"""
            UPDATE videos
            SET status = ?{processed_at_sql}, error_message = ?
            WHERE id = ?
            """,
            (status, error_message, video_id),
        )
        await conn.commit()
        return await self.get_video(video_id)

    async def claim_video_for_processing(self, video_id: str) -> dict | None:
        """Atomically claim a pending or failed video for processing."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            UPDATE videos
            SET status = 'processing'
            WHERE id = ? AND status IN ('pending', 'failed')
            """,
            (video_id,),
        )
        await conn.commit()
        if cursor.rowcount != 1:
            return None
        return await self.get_video(video_id)

    async def create_document(
        self,
        *,
        document_id: str,
        video_id: str,
        file_path: str,
        chunk_count: int = 0,
        is_indexed: bool = False,
    ) -> dict:
        """Create a document record and return it."""
        conn = self._require_conn()
        await conn.execute(
            """
            INSERT INTO documents (id, video_id, file_path, chunk_count, is_indexed)
            VALUES (?, ?, ?, ?, ?)
            """,
            (document_id, video_id, file_path, chunk_count, int(is_indexed)),
        )
        await conn.commit()

        document = await self.get_document(document_id)
        if document is None:
            raise RuntimeError("Created document could not be loaded")
        return document

    async def get_document(self, document_id: str) -> dict | None:
        """Return a document record by ID, or None when missing."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT id, video_id, file_path, chunk_count, is_indexed, indexed_at
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        )
        row = await cursor.fetchone()
        return self._row_to_dict(row) if row else None

    async def list_documents(self) -> list[dict]:
        """List document records with newest records first."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT id, video_id, file_path, chunk_count, is_indexed, indexed_at
            FROM documents
            ORDER BY rowid DESC
            """
        )
        rows = await cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    async def list_documents_for_video(self, video_id: str) -> list[dict]:
        """List document records for a video with newest records first."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT id, video_id, file_path, chunk_count, is_indexed, indexed_at
            FROM documents
            WHERE video_id = ?
            ORDER BY rowid DESC
            """,
            (video_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document record. Return True when a row was removed."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "DELETE FROM documents WHERE id = ?", (document_id,)
        )
        await conn.commit()
        return cursor.rowcount == 1

    async def mark_document_indexed(
        self, document_id: str, *, chunk_count: int
    ) -> dict | None:
        """Mark a document as indexed and return the updated record."""
        conn = self._require_conn()
        await conn.execute(
            """
            UPDATE documents
            SET chunk_count = ?, is_indexed = 1, indexed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (chunk_count, document_id),
        )
        await conn.commit()
        return await self.get_document(document_id)

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
