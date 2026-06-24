"""Database-based persistence for model settings.

Manages model presets in the SQLite database. None values mean "keep the
existing value" so the API can accept partial updates (e.g. masked keys).
"""

import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigStore:
    def __init__(self, db_path: Path | str) -> None:
        """
        Initialize config store with database path.

        Args:
            db_path: Path to memento.db
        """
        self.db_path = Path(db_path)

    def update_models(self, models_update: dict) -> None:
        """
        Merge model config updates into the active preset for each model.

        Args:
            models_update: Dict mapping model_name to field updates.
                          None values preserve existing field values.
        """
        if not self.db_path.exists():
            logger.warning(f"DB not found at {self.db_path}, skipping model update")
            return

        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row

            for model_name, fields in models_update.items():
                # Get active preset config
                cursor = conn.execute(
                    """
                    SELECT mp.id, mp.config
                    FROM active_preset ap
                    JOIN model_presets mp ON ap.preset_id = mp.id
                    WHERE ap.model_name = ?
                    """,
                    (model_name,),
                )
                row = cursor.fetchone()

                if not row:
                    logger.warning(f"No active preset for {model_name}, skipping update")
                    continue

                preset_id = row["id"]
                config = json.loads(row["config"])

                # Merge updates (skip None values)
                for key, value in fields.items():
                    if value is not None:
                        config[key] = value

                # Write back to DB
                conn.execute(
                    """
                    UPDATE model_presets
                    SET config = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (json.dumps(config), preset_id),
                )

            conn.commit()

        except Exception as e:
            logger.error(f"Failed to update models in DB: {e}")
            raise
        finally:
            conn.close()

    def _get_app_config_json(self, key: str) -> dict | None:
        """
        Get JSON config from app_config table.

        Args:
            key: Configuration key

        Returns:
            Parsed JSON dict or None if key doesn't exist
        """
        if not self.db_path.exists():
            return None

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT value FROM app_config WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
            return None
        finally:
            conn.close()

    def _set_app_config_json(self, key: str, value: dict) -> None:
        """
        Set JSON config in app_config table.

        Args:
            key: Configuration key
            value: Dict to store as JSON
        """
        if not self.db_path.exists():
            logger.warning(f"DB not found at {self.db_path}, skipping config write")
            return

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO app_config (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, json.dumps(value)),
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to write app_config key {key}: {e}")
            raise
        finally:
            conn.close()

    def update_video_processing(self, updates: dict) -> None:
        """
        Update video_processing config fields.

        Args:
            updates: Dict of fields to update
        """
        current = self._get_app_config_json("video_processing") or {}
        current.update(updates)
        self._set_app_config_json("video_processing", current)
