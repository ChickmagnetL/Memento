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

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
