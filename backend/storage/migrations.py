"""Schema migrations keyed off PRAGMA user_version."""

import logging

import aiosqlite

logger = logging.getLogger(__name__)


async def _migrate_documents_video_id_nullable(conn: aiosqlite.Connection) -> None:
    """Migration 1: make documents.video_id nullable with ON DELETE SET NULL.

    Rebuilds the documents table (SQLite cannot ALTER a column's NOT NULL or
    FK action in place). documents is only a child table, so dropping it does
    not violate any foreign keys.

    Handles both old schema (is_indexed) and new schema (status) column names
    so the migration works on databases at any schema version.
    """
    cursor = await conn.execute("PRAGMA table_info(documents)")
    rows = await cursor.fetchall()
    columns = [r[1] for r in rows]
    index_col = "is_indexed" if "is_indexed" in columns else "status"

    await conn.executescript(
        f"""
        CREATE TABLE documents_new (
            id TEXT PRIMARY KEY,
            video_id TEXT,
            file_path TEXT NOT NULL,
            chunk_count INTEGER DEFAULT 0,
            {index_col} {'BOOLEAN DEFAULT 0' if index_col == 'is_indexed' else "TEXT DEFAULT 'raw'"},
            indexed_at TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE SET NULL
        );
        INSERT INTO documents_new (id, video_id, file_path, chunk_count, {index_col}, indexed_at)
        SELECT id, video_id, file_path, chunk_count, {index_col}, indexed_at FROM documents;
        DROP TABLE documents;
        ALTER TABLE documents_new RENAME TO documents;
        CREATE INDEX IF NOT EXISTS idx_documents_video_id ON documents(video_id);
        """
    )
    await conn.commit()


async def _migrate_videos_add_author_id(conn: aiosqlite.Connection) -> None:
    """Migration 2: add author_id TEXT column to videos table.

    Stores platform-native author identifier (B站 owner.mid, 抖音 sec_uid).
    Existing rows get NULL.
    """
    cursor = await conn.execute("PRAGMA table_info(videos)")
    rows = await cursor.fetchall()
    if not any(r[1] == "author_id" for r in rows):
        await conn.execute("ALTER TABLE videos ADD COLUMN author_id TEXT")
        await conn.commit()


async def _migrate_add_presets_and_app_config(conn: aiosqlite.Connection) -> None:
    """Migration 3: DEPRECATED, superseded by migration 4.

    This migration is now a no-op. Migration 4 handles both fresh installs
    and upgrades from any prior state.
    """
    pass


async def _migrate_fix_spec_compliance(conn: aiosqlite.Connection) -> None:
    """Migration 4: fix spec compliance issues.

    Rebuilds tables to match specification:
    - Rename transcription_presets -> model_presets (preset_id -> id, provider -> model_name)
    - Add UNIQUE(model_name, name) constraint
    - Rebuild active_preset with model_name as PK
    - Fix app_config.value to allow NULL

    Handles two scenarios:
    1. Upgrade from migration 3: converts old schema to new schema
    2. Fresh install: creates new schema directly
    """
    # Check if old tables exist (migration 3 was applied)
    cursor = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='transcription_presets'"
    )
    has_old_table = await cursor.fetchone() is not None

    # Check if new tables already exist
    cursor = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='model_presets'"
    )
    has_new_table = await cursor.fetchone() is not None

    if has_new_table and not has_old_table:
        # Already migrated, skip
        return

    if has_old_table:
        # Migrate data from old structure to new structure
        await conn.executescript(
            """
            -- Create new model_presets table
            CREATE TABLE model_presets (
                id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                name TEXT NOT NULL,
                config TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(model_name, name)
            );

            -- Migrate data: preset_id -> id, provider -> model_name
            INSERT INTO model_presets (id, model_name, name, config, created_at, updated_at)
            SELECT preset_id, provider, name, config, created_at, created_at
            FROM transcription_presets;

            -- Create new active_preset table with model_name as PK
            CREATE TABLE active_preset_new (
                model_name TEXT PRIMARY KEY,
                preset_id TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (preset_id) REFERENCES model_presets(id) ON DELETE SET NULL
            );

            -- Migrate active preset: lookup provider from old preset
            INSERT INTO active_preset_new (model_name, preset_id, updated_at)
            SELECT tp.provider, ap.preset_id, ap.updated_at
            FROM active_preset ap
            JOIN transcription_presets tp ON ap.preset_id = tp.preset_id
            WHERE ap.id = 1 AND ap.preset_id IS NOT NULL;

            -- Rebuild app_config with nullable value
            CREATE TABLE app_config_new (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            INSERT INTO app_config_new (key, value, updated_at)
            SELECT key, value, updated_at FROM app_config;

            -- Drop old tables
            DROP TABLE active_preset;
            DROP TABLE transcription_presets;
            DROP TABLE app_config;

            -- Rename new tables
            ALTER TABLE active_preset_new RENAME TO active_preset;
            ALTER TABLE app_config_new RENAME TO app_config;
            """
        )
    else:
        # Fresh install: create tables with correct schema directly
        await conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS model_presets (
                id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                name TEXT NOT NULL,
                config TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(model_name, name)
            );

            CREATE TABLE IF NOT EXISTS active_preset (
                model_name TEXT PRIMARY KEY,
                preset_id TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (preset_id) REFERENCES model_presets(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
    await conn.commit()


async def _migrate_documents_add_status(conn: aiosqlite.Connection) -> None:
    """Migration 5: replace is_indexed BOOLEAN with status TEXT.

    1. Add status TEXT DEFAULT 'raw' column
    2. Convert is_indexed = 1 rows to status = 'indexed'
    3. Deduplicate: for %.clean.md files, delete the matching raw document
       (same video_id, file_path without .clean)
    4. Drop the is_indexed column (SQLite 3.35+)
    """
    cursor = await conn.execute("PRAGMA table_info(documents)")
    rows = await cursor.fetchall()
    columns = [r[1] for r in rows]

    if "status" in columns:
        return  # Already migrated

    if "is_indexed" not in columns:
        # Fresh install with new schema — nothing to convert
        return

    # 1. Add status column
    await conn.execute(
        "ALTER TABLE documents ADD COLUMN status TEXT DEFAULT 'raw'"
    )

    # 2. Convert indexed flag
    await conn.execute(
        "UPDATE documents SET status = 'indexed' WHERE is_indexed = 1"
    )

    # 3. Deduplicate: when a .clean.md version exists, remove the raw version
    await conn.execute(
        """
        DELETE FROM documents
        WHERE id IN (
            SELECT raw.id
            FROM documents clean
            JOIN documents raw
                ON (raw.video_id = clean.video_id
                    OR (raw.video_id IS NULL AND clean.video_id IS NULL))
                AND raw.file_path = REPLACE(clean.file_path, '.clean.md', '.md')
            WHERE clean.file_path LIKE '%.clean.md'
        )
        """
    )

    # 4. Drop the old column
    await conn.execute("ALTER TABLE documents DROP COLUMN is_indexed")

    await conn.commit()


async def _migrate_documents_add_created_at(conn: aiosqlite.Connection) -> None:
    """Migration 6: add created_at column to documents table."""
    cursor = await conn.execute("PRAGMA table_info(documents)")
    rows = await cursor.fetchall()
    if any(r[1] == "created_at" for r in rows):
        return  # Already migrated

    await conn.execute(
        "ALTER TABLE documents ADD COLUMN created_at TIMESTAMP"
    )
    await conn.execute(
        "UPDATE documents SET created_at = COALESCE(indexed_at, CURRENT_TIMESTAMP)"
    )
    await conn.commit()


async def _migrate_documents_add_title_author(conn: aiosqlite.Connection) -> None:
    """Migration 7: add title and author columns to documents table.

    Populated from markdown header for standalone documents (video_id IS NULL).
    Video-linked documents inherit title/author from the videos table via JOIN.
    """
    cursor = await conn.execute("PRAGMA table_info(documents)")
    rows = await cursor.fetchall()
    columns = [r[1] for r in rows]

    if "title" not in columns:
        await conn.execute("ALTER TABLE documents ADD COLUMN title TEXT")
    if "author" not in columns:
        await conn.execute("ALTER TABLE documents ADD COLUMN author TEXT")
    await conn.commit()


async def _migrate_documents_add_author_column(conn: aiosqlite.Connection) -> None:
    """Migration 8: add author column if migration 7 only added title.

    Migration 7 was deployed incrementally; some databases may have
    user_version 7 with title but not author.
    """
    cursor = await conn.execute("PRAGMA table_info(documents)")
    rows = await cursor.fetchall()
    if any(r[1] == "author" for r in rows):
        return

    await conn.execute("ALTER TABLE documents ADD COLUMN author TEXT")
    await conn.commit()


async def _migrate_add_chat_tables(conn: aiosqlite.Connection) -> None:
    """Migration 9: create chat_sessions and chat_messages tables.

    Idempotent (CREATE TABLE IF NOT EXISTS) — safe for both fresh installs
    (tables created by schema.sql) and upgrades from older databases.
    """
    await conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT 'New Chat',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
        """
    )
    await conn.commit()


async def _migrate_documents_add_summary_brief(conn: aiosqlite.Connection) -> None:
    """Migration 10: add summary and brief columns to documents table.

    summary stores the L2 paragraph summary and brief stores the L3
    one-sentence description, both generated when a document is cleaned.
    """
    cursor = await conn.execute("PRAGMA table_info(documents)")
    rows = await cursor.fetchall()
    columns = [r[1] for r in rows]

    if "summary" not in columns:
        await conn.execute("ALTER TABLE documents ADD COLUMN summary TEXT")
    if "brief" not in columns:
        await conn.execute("ALTER TABLE documents ADD COLUMN brief TEXT")
    await conn.commit()


async def _migrate_add_memories_table(conn: aiosqlite.Connection) -> None:
    """Migration 11: create memories table for cross-session user profile/preferences.

    Idempotent (CREATE TABLE IF NOT EXISTS).
    """
    await conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    await conn.commit()


_MIGRATIONS = [
    _migrate_documents_video_id_nullable,
    _migrate_videos_add_author_id,
    _migrate_add_presets_and_app_config,
    _migrate_fix_spec_compliance,
    _migrate_documents_add_status,
    _migrate_documents_add_created_at,
    _migrate_documents_add_title_author,
    _migrate_documents_add_author_column,
    _migrate_add_chat_tables,
    _migrate_documents_add_summary_brief,
    _migrate_add_memories_table,
]


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
