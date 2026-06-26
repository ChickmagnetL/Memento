"""
Migrate config.local.yaml to database.

This migration runs once on startup to move user configuration from
config.local.yaml into the database. After successful migration, the
file is renamed to config.local.yaml.bak as a backup.

Author: Memento Team
Last Updated: 2026-06-23
"""

import json
import logging
from pathlib import Path

from storage.sqlite_client import SQLiteClient
from config.settings import _load_yaml_data, resolve_project_root

logger = logging.getLogger(__name__)

# Supported model types for migration
SUPPORTED_MODELS = ["asr", "chat", "embedding"]


async def migrate_config_to_db(sqlite: SQLiteClient) -> None:
    """
    Migrate config.local.yaml to database if needed.

    Idempotency: skips migration if model_presets table has any records.

    Migration steps:
    1. Check if migration already ran (model_presets table non-empty)
    2. Load config.local.yaml (skip if file missing)
    3. Migrate models.* to model_presets + set active presets
    4. Migrate other sections (storage, video_processing, rag) to app_config
    5. Rename config.local.yaml to config.local.yaml.bak

    Args:
        sqlite: Connected SQLiteClient instance
    """
    # Step 1: Check idempotency - skip if any presets exist
    existing_presets = await sqlite.list_presets()
    if existing_presets:
        logger.info("Migration skipped: model_presets table already has records")
        return

    # Step 2: Load config.local.yaml
    project_root = resolve_project_root()
    local_config_path = project_root / "config.local.yaml"

    if not local_config_path.exists():
        logger.info("No config.local.yaml found, migration skipped")
        return

    config_data = _load_yaml_data(local_config_path)
    if not config_data:
        logger.info("config.local.yaml is empty, migration skipped")
        return

    logger.info("Starting migration from config.local.yaml to database")

    # Step 3: Migrate models.* to model_presets + active_preset
    models_config = config_data.get("models", {})
    for model_name in SUPPORTED_MODELS:
        if model_name not in models_config:
            continue

        model_config = models_config[model_name]

        # Convert to dict format (yaml.safe_load returns dict)
        config_dict = dict(model_config)

        # Create preset with name "Default"
        preset = await sqlite.create_preset(
            name="Default",
            model_name=model_name,
            config=config_dict
        )

        # Set as active preset
        await sqlite.set_active_preset(model_name, preset["id"])

        logger.info(f"Migrated {model_name} model preset: {preset['id']}")

    # Step 4: Migrate other sections to app_config
    for key in ["storage", "video_processing", "rag"]:
        if key in config_data:
            value_json = json.dumps(config_data[key], ensure_ascii=False)
            await sqlite.set_app_config(key, value_json)
            logger.info(f"Migrated app_config key: {key}")

    # Step 5: Rename config.local.yaml to .bak
    backup_path = local_config_path.with_suffix(local_config_path.suffix + ".bak")
    local_config_path.rename(backup_path)
    logger.info(f"Migration complete. Renamed {local_config_path.name} to {backup_path.name}")
