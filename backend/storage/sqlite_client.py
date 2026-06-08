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
            SELECT id, platform, title, author, duration, url, status, created_at, processed_at
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
            SELECT id, platform, title, author, duration, url, status, created_at, processed_at
            FROM videos
            WHERE id = ?
            """,
            (video_id,),
        )
        row = await cursor.fetchone()
        return self._row_to_dict(row) if row else None

    async def update_video_status(self, video_id: str, status: str) -> dict | None:
        """Update a video status and return the updated record."""
        conn = self._require_conn()
        processed_at_sql = (
            ", processed_at = CURRENT_TIMESTAMP" if status in {"completed", "failed"} else ""
        )
        await conn.execute(
            f"""
            UPDATE videos
            SET status = ?{processed_at_sql}
            WHERE id = ?
            """,
            (status, video_id),
        )
        await conn.commit()
        return await self.get_video(video_id)

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
