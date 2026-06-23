"""
SQLite database client for Memento metadata storage.

Phase 1 scope: Initialize database connection and create tables from schema.
CRUD operations are added in Phase 2 when video processing is implemented.

Author: Memento Team
Last Updated: 2026-06-07
"""

import json
import uuid
import aiosqlite
from pathlib import Path

from storage.migrations import run_migrations


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

        await run_migrations(self._conn)

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
        author_id: str | None = None,
        duration: int | None = None,
    ) -> dict:
        """Create a pending video record and return it."""
        conn = self._require_conn()
        await conn.execute(
            """
            INSERT INTO videos (id, platform, title, author, author_id, duration, url, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (video_id, platform, title, author, author_id, duration, url),
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
            SELECT id, platform, title, author, author_id, duration, url, status, error_message, created_at, processed_at
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
            SELECT id, platform, title, author, author_id, duration, url, status, error_message, created_at, processed_at
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
        """Atomically claim a pending, failed, or completed video for processing."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            UPDATE videos
            SET status = 'processing'
            WHERE id = ? AND status IN ('pending', 'failed', 'completed')
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
        video_id: str | None = None,
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

    async def get_document_by_video_and_path(
        self, video_id: str, file_path: str
    ) -> dict | None:
        """Return a document record matching a video and exact file path."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT id, video_id, file_path, chunk_count, is_indexed, indexed_at
            FROM documents
            WHERE video_id = ? AND file_path = ?
            ORDER BY rowid DESC
            LIMIT 1
            """,
            (video_id, file_path),
        )
        row = await cursor.fetchone()
        return self._row_to_dict(row) if row else None

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document record. Return True when a row was removed."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "DELETE FROM documents WHERE id = ?", (document_id,)
        )
        await conn.commit()
        return cursor.rowcount == 1

    async def delete_video(self, video_id: str) -> bool:
        """Delete a video record. Return True when a row was removed.

        Child documents keep their rows; their video_id is SET NULL by the
        foreign key (knowledge-base content is preserved).
        """
        conn = self._require_conn()
        cursor = await conn.execute(
            "DELETE FROM videos WHERE id = ?", (video_id,)
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

    async def reset_document_indexing(self, document_id: str) -> dict | None:
        """Reset indexing metadata and return the updated document."""
        conn = self._require_conn()
        await conn.execute(
            """
            UPDATE documents
            SET chunk_count = 0, is_indexed = 0, indexed_at = NULL
            WHERE id = ?
            """,
            (document_id,),
        )
        await conn.commit()
        return await self.get_document(document_id)

    # ===== Transcription Preset CRUD =====

    async def create_preset(
        self, *, name: str, provider: str, config: dict
    ) -> dict:
        """Create a transcription preset and return it."""
        conn = self._require_conn()
        preset_id = str(uuid.uuid4())
        config_json = json.dumps(config)
        await conn.execute(
            """
            INSERT INTO transcription_presets (preset_id, name, provider, config)
            VALUES (?, ?, ?, ?)
            """,
            (preset_id, name, provider, config_json),
        )
        await conn.commit()

        preset = await self.get_preset(preset_id)
        if preset is None:
            raise RuntimeError("Created preset could not be loaded")
        return preset

    async def get_preset(self, preset_id: str) -> dict | None:
        """Return a preset record by ID, or None when missing."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT preset_id, name, provider, config, created_at
            FROM transcription_presets
            WHERE preset_id = ?
            """,
            (preset_id,),
        )
        row = await cursor.fetchone()
        return self._row_to_dict(row) if row else None

    async def list_presets(self) -> list[dict]:
        """List all presets with newest records first."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT preset_id, name, provider, config, created_at
            FROM transcription_presets
            ORDER BY rowid DESC
            """
        )
        rows = await cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    async def update_preset(
        self, *, preset_id: str, name: str, provider: str, config: dict
    ) -> dict | None:
        """Update a preset and return the updated record."""
        conn = self._require_conn()
        config_json = json.dumps(config)
        cursor = await conn.execute(
            """
            UPDATE transcription_presets
            SET name = ?, provider = ?, config = ?
            WHERE preset_id = ?
            """,
            (name, provider, config_json, preset_id),
        )
        await conn.commit()
        if cursor.rowcount == 0:
            return None
        return await self.get_preset(preset_id)

    async def delete_preset(self, preset_id: str) -> bool:
        """Delete a preset. Return True when a row was removed.

        ON DELETE SET NULL ensures active_preset.preset_id is cleared if referenced.
        """
        conn = self._require_conn()
        cursor = await conn.execute(
            "DELETE FROM transcription_presets WHERE preset_id = ?", (preset_id,)
        )
        await conn.commit()
        return cursor.rowcount == 1

    # ===== Active Preset =====

    async def set_active_preset(self, preset_id: str) -> None:
        """Set the active transcription preset (upsert singleton)."""
        conn = self._require_conn()
        await conn.execute(
            """
            INSERT INTO active_preset (id, preset_id, updated_at)
            VALUES (1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET preset_id = excluded.preset_id, updated_at = CURRENT_TIMESTAMP
            """,
            (preset_id,),
        )
        await conn.commit()

    async def get_active_preset(self) -> dict | None:
        """Return the active preset record, or None if not set or preset deleted."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT preset_id, updated_at
            FROM active_preset
            WHERE id = 1 AND preset_id IS NOT NULL
            """
        )
        row = await cursor.fetchone()
        return self._row_to_dict(row) if row else None

    async def clear_active_preset(self) -> None:
        """Clear the active preset (set preset_id to NULL)."""
        conn = self._require_conn()
        await conn.execute(
            """
            UPDATE active_preset
            SET preset_id = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """
        )
        await conn.commit()

    # ===== App Config =====

    async def set_app_config(self, key: str, value: dict) -> None:
        """Set an app config entry (upsert). Value is JSON-serialized."""
        conn = self._require_conn()
        value_json = json.dumps(value)
        await conn.execute(
            """
            INSERT INTO app_config (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (key, value_json),
        )
        await conn.commit()

    async def get_app_config(self, key: str) -> dict | None:
        """Return app config value as dict, or None if key missing."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT value
            FROM app_config
            WHERE key = ?
            """,
            (key,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return json.loads(row[0])

    async def delete_app_config(self, key: str) -> bool:
        """Delete an app config entry. Return True when a row was removed."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "DELETE FROM app_config WHERE key = ?", (key,)
        )
        await conn.commit()
        return cursor.rowcount == 1

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
