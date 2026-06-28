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
        status: str | None = None,
        title: str | None = None,
        author: str | None = None,
    ) -> dict:
        """Create a document record and return it."""
        if status is None:
            status = 'indexed' if is_indexed else 'raw'
        conn = self._require_conn()
        await conn.execute(
            """
            INSERT INTO documents (id, video_id, file_path, chunk_count, status, title, author)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (document_id, video_id, file_path, chunk_count, status, title, author),
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
            SELECT id, video_id, file_path, chunk_count, status,
                   indexed_at, created_at,
                   COALESCE(title, 'Untitled') AS title,
                   COALESCE(author, 'Unknown') AS author
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
            SELECT d.id, d.video_id, d.file_path, d.chunk_count, d.status,
                   d.indexed_at, d.created_at,
                   COALESCE(v.title, d.title, 'Untitled') AS title,
                   COALESCE(v.author, d.author, 'Unknown') AS author
            FROM documents d
            LEFT JOIN videos v ON d.video_id = v.id
            ORDER BY d.rowid DESC
            """
        )
        rows = await cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    async def list_documents_for_video(self, video_id: str) -> list[dict]:
        """List document records for a video with newest records first."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT id, video_id, file_path, chunk_count, status,
                   indexed_at, created_at,
                   COALESCE(title, 'Untitled') AS title,
                   COALESCE(author, 'Unknown') AS author
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
            SELECT id, video_id, file_path, chunk_count, status,
                   indexed_at, created_at,
                   COALESCE(title, 'Untitled') AS title,
                   COALESCE(author, 'Unknown') AS author
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
            SET chunk_count = ?, status = 'indexed', indexed_at = CURRENT_TIMESTAMP
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
            SET chunk_count = 0, status = 'raw', indexed_at = NULL
            WHERE id = ?
            """,
            (document_id,),
        )
        await conn.commit()
        return await self.get_document(document_id)

    async def update_document_path(self, document_id: str, file_path: str) -> dict | None:
        """Update a document's file_path and return the updated record."""
        conn = self._require_conn()
        await conn.execute(
            "UPDATE documents SET file_path = ? WHERE id = ?",
            (file_path, document_id),
        )
        await conn.commit()
        return await self.get_document(document_id)

    # ===== Model Preset CRUD =====

    async def create_preset(
        self, *, name: str, model_name: str, config: dict
    ) -> dict:
        """Create a model preset and return it."""
        conn = self._require_conn()
        preset_id = str(uuid.uuid4())
        config_json = json.dumps(config)
        await conn.execute(
            """
            INSERT INTO model_presets (id, model_name, name, config)
            VALUES (?, ?, ?, ?)
            """,
            (preset_id, model_name, name, config_json),
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
            SELECT id, model_name, name, config, created_at, updated_at
            FROM model_presets
            WHERE id = ?
            """,
            (preset_id,),
        )
        row = await cursor.fetchone()
        return self._row_to_dict(row) if row else None

    async def list_presets(self, model_name: str | None = None) -> list[dict]:
        """List all presets, optionally filtered by model_name, with newest records first."""
        conn = self._require_conn()
        if model_name:
            cursor = await conn.execute(
                """
                SELECT id, model_name, name, config, created_at, updated_at
                FROM model_presets
                WHERE model_name = ?
                ORDER BY rowid DESC
                """,
                (model_name,),
            )
        else:
            cursor = await conn.execute(
                """
                SELECT id, model_name, name, config, created_at, updated_at
                FROM model_presets
                ORDER BY rowid DESC
                """
            )
        rows = await cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    async def update_preset(
        self, *, preset_id: str, name: str, model_name: str, config: dict
    ) -> dict | None:
        """Update a preset and return the updated record."""
        conn = self._require_conn()
        config_json = json.dumps(config)
        cursor = await conn.execute(
            """
            UPDATE model_presets
            SET name = ?, model_name = ?, config = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (name, model_name, config_json, preset_id),
        )
        await conn.commit()
        if cursor.rowcount == 0:
            return None
        return await self.get_preset(preset_id)

    async def delete_preset(self, preset_id: str) -> bool:
        """Delete a preset. Return True when a row was removed.

        ON DELETE SET NULL ensures active_preset.preset_id is set to NULL.
        """
        conn = self._require_conn()
        cursor = await conn.execute(
            "DELETE FROM model_presets WHERE id = ?", (preset_id,)
        )
        await conn.commit()
        return cursor.rowcount == 1

    # ===== Active Preset =====

    async def set_active_preset(self, model_name: str, preset_id: str) -> None:
        """Set the active preset for a model (upsert)."""
        conn = self._require_conn()
        await conn.execute(
            """
            INSERT INTO active_preset (model_name, preset_id, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(model_name) DO UPDATE SET preset_id = excluded.preset_id, updated_at = CURRENT_TIMESTAMP
            """,
            (model_name, preset_id),
        )
        await conn.commit()

    async def get_active_preset(self, model_name: str) -> dict | None:
        """Return the active preset for a model, or None if not set."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT model_name, preset_id, updated_at
            FROM active_preset
            WHERE model_name = ?
            """,
            (model_name,),
        )
        row = await cursor.fetchone()
        return self._row_to_dict(row) if row else None

    async def clear_active_preset(self, model_name: str) -> None:
        """Clear the active preset for a model."""
        conn = self._require_conn()
        await conn.execute(
            """
            DELETE FROM active_preset
            WHERE model_name = ?
            """,
            (model_name,),
        )
        await conn.commit()

    # ===== Chat Sessions / Messages =====

    async def create_chat_session(self, title: str | None = None) -> dict:
        """Create a chat session and return it. Default title 'New Chat'."""
        conn = self._require_conn()
        session_id = uuid.uuid4().hex
        await conn.execute(
            """
            INSERT INTO chat_sessions (id, title)
            VALUES (?, COALESCE(?, 'New Chat'))
            """,
            (session_id, title),
        )
        await conn.commit()
        session = await self.get_chat_session(session_id)
        if session is None:
            raise RuntimeError("Created chat session could not be loaded")
        return session

    async def get_chat_session(self, session_id: str) -> dict | None:
        """Return a chat session by ID, or None when missing."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM chat_sessions
            WHERE id = ?
            """,
            (session_id,),
        )
        row = await cursor.fetchone()
        return self._row_to_dict(row) if row else None

    async def list_chat_sessions(self) -> list[dict]:
        """List chat sessions with most-recently-active first."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM chat_sessions
            ORDER BY updated_at DESC, id DESC
            """
        )
        rows = await cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    async def rename_chat_session(self, session_id: str, title: str) -> dict | None:
        """Rename a chat session and return the updated record."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            UPDATE chat_sessions
            SET title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (title, session_id),
        )
        await conn.commit()
        if cursor.rowcount == 0:
            return None
        return await self.get_chat_session(session_id)

    async def delete_chat_session(self, session_id: str) -> bool:
        """Delete a chat session. Messages cascade-deleted by FK. Return True when removed."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "DELETE FROM chat_sessions WHERE id = ?", (session_id,)
        )
        await conn.commit()
        return cursor.rowcount == 1

    async def add_chat_message(
        self, *, session_id: str, role: str, content: str
    ) -> dict:
        """Append a message to a session, bump session.updated_at, return the message row."""
        conn = self._require_conn()
        message_id = uuid.uuid4().hex
        await conn.execute(
            """
            INSERT INTO chat_messages (id, session_id, role, content)
            VALUES (?, ?, ?, ?)
            """,
            (message_id, session_id, role, content),
        )
        await conn.execute(
            "UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,),
        )
        await conn.commit()
        cursor = await conn.execute(
            """
            SELECT id, session_id, role, content, created_at
            FROM chat_messages WHERE id = ?
            """,
            (message_id,),
        )
        row = await cursor.fetchone()
        return self._row_to_dict(row)

    async def list_chat_messages(self, session_id: str) -> list[dict]:
        """List messages for a session, oldest first."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT id, session_id, role, content, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    async def get_chat_history(self, session_id: str) -> list[tuple[str, str]]:
        """Return prior messages as (role, content) tuples for agent message_history rebuild."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT role, content FROM chat_messages
            WHERE session_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [(row["role"], row["content"]) for row in rows]

    # ===== App Config =====

    async def set_app_config(self, key: str, value: str | None) -> None:
        """Set an app config entry (upsert). Value is stored as-is (TEXT or NULL)."""
        conn = self._require_conn()
        await conn.execute(
            """
            INSERT INTO app_config (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )
        await conn.commit()

    async def get_app_config(self, key: str) -> str | None:
        """Return app config value as string, or None if key missing."""
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
        return row[0] if row else None

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
