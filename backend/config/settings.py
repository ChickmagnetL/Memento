"""
Configuration management for Memento backend.

This module loads configuration from YAML files and environment variables.
Settings are validated using Pydantic models.

Priority (highest to lowest):
1. Environment variables
2. Database (model presets + app_config)
3. config.local.yaml (git-ignored, for local overrides)
4. config.yaml (user configuration)
5. default.yaml (default configuration)

Author: Memento Team
Last Updated: 2026-06-23
"""

import json
import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

logger = logging.getLogger(__name__)


def resolve_backend_dir() -> Path:
    """Backend root: the PyInstaller bundle dir when frozen, else this package's parent."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).parent.parent


def resolve_project_root(backend_dir: Path | None = None) -> Path:
    """Project root containing user config files."""
    if override := os.environ.get("MEMENTO_PROJECT_ROOT"):
        return Path(override)
    return (backend_dir or resolve_backend_dir()).parent


def _load_yaml_data(config_path: Path | str) -> dict[str, Any]:
    config_path = Path(config_path)

    if not config_path.exists():
        return {}

    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


# ============================================================
# SECTION 1: Model Configuration
# ============================================================

class ModelConfig(BaseModel):
    """Configuration for a model service (ASR/Embedding/Chat)."""

    provider: Literal["local", "ollama", "openai", "cloud"] = "cloud"
    endpoint: str | None = None
    api_key: str | None = None
    model: str | None = None
    protocol: Literal["transcriptions", "chat_audio"] | None = None


class ModelsConfig(BaseModel):
    """All model service configurations."""

    asr: ModelConfig = Field(default_factory=lambda: ModelConfig(provider="local"))
    embedding: ModelConfig = Field(default_factory=lambda: ModelConfig(provider="ollama"))
    chat: ModelConfig = Field(default_factory=lambda: ModelConfig(provider="cloud"))


# ============================================================
# SECTION 2: Storage Configuration
# ============================================================

class StorageConfig(BaseModel):
    """Storage paths and options."""

    data_dir: Path = Path.home() / "memento_data"
    keep_videos: bool = False


# ============================================================
# SECTION 3: Video Processing Configuration
# ============================================================

class VideoProcessingConfig(BaseModel):
    """Video processing options."""

    auto_clean: bool = True
    preserve_timestamp: bool = True
    bilibili_cookie: str = ""
    douyin_cookie: str = ""
    douyin_fetcher_endpoint: str = "http://localhost:8002"
    ocr_region: list[float] = [0.74, 0.94, 0.08, 0.92]  # y_min, y_max, x_min, x_max


# ============================================================
# SECTION 4: RAG Configuration
# ============================================================

class RAGConfig(BaseModel):
    """RAG indexing and retrieval configuration."""

    chunk_size: int = 800
    overlap: int = 80
    top_k: int = 5
    hybrid_weights: dict[str, float] = {"bm25": 0.3, "vector": 0.7}
    # Must match the embedding model's output dimension.
    vector_size: int = 768


# ============================================================
# SECTION 5: Main Settings
# ============================================================

class Settings(BaseSettings):
    """
    Main application settings.

    Loads configuration from YAML files and environment variables.
    """

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Logging
    log_level: str = "INFO"

    # Component configurations
    storage: StorageConfig = Field(default_factory=StorageConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    video_processing: VideoProcessingConfig = Field(default_factory=VideoProcessingConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return env_settings, dotenv_settings, init_settings, file_secret_settings

    @classmethod
    def load_from_yaml(cls, config_path: Path | str) -> "Settings":
        """
        Load settings from YAML file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            Settings instance with loaded configuration
        """
        return cls(**_load_yaml_data(config_path))


# ============================================================
# SECTION 6: Settings Factory
# ============================================================

def _load_db_config(db_path: Path) -> dict[str, Any]:
    """
    Load configuration from SQLite database.

    Reads:
    - app_config table: storage/video_processing/rag sections (JSON)
    - active_preset + model_presets: asr/chat/embedding model configs

    Returns:
        Configuration dict with models and section overrides
    """
    if not db_path.exists():
        return {}

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        db_config: dict[str, Any] = {}

        # Load app_config sections
        try:
            cursor = conn.execute("SELECT key, value FROM app_config")
            rows = cursor.fetchall()
            for row in rows:
                key = row["key"]
                value = row["value"]
                if value is not None:
                    try:
                        db_config[key] = json.loads(value)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in app_config.{key}, skipping")
        except sqlite3.OperationalError as e:
            logger.debug(f"app_config table read failed: {e}, skipping")

        # Load active model presets
        try:
            db_config["models"] = {}
            for model_name in ["asr", "chat", "embedding"]:
                cursor = conn.execute(
                    """
                    SELECT mp.config
                    FROM active_preset ap
                    JOIN model_presets mp ON ap.preset_id = mp.id
                    WHERE ap.model_name = ?
                    """,
                    (model_name,),
                )
                row = cursor.fetchone()
                if row and row["config"]:
                    try:
                        preset_config = json.loads(row["config"])
                        # Only override if preset config is non-empty
                        if preset_config:
                            db_config["models"][model_name] = preset_config
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in preset for {model_name}, skipping")
        except sqlite3.OperationalError as e:
            logger.debug(f"model_presets table read failed: {e}, skipping")

        return db_config

    except Exception as e:
        logger.warning(f"Failed to load DB config: {e}, using YAML only")
        return {}
    finally:
        conn.close()


def get_settings() -> Settings:
    """
    Get application settings with layered configuration.

    Load order (later overrides earlier):
    1. default.yaml
    2. ../config.yaml (user config)
    3. ../config.local.yaml (local overrides, git-ignored)
    4. Database (model presets + app_config)
    5. Environment variables

    Returns:
        Settings instance
    """
    backend_dir = resolve_backend_dir()
    project_root = resolve_project_root(backend_dir)

    # Load YAML configs
    default_config_path = backend_dir / "config" / "default.yaml"
    user_config_path = project_root / "config.yaml"
    local_config_path = project_root / "config.local.yaml"

    config_data = _load_yaml_data(default_config_path)
    config_data = _merge_dicts(config_data, _load_yaml_data(user_config_path))
    config_data = _merge_dicts(config_data, _load_yaml_data(local_config_path))

    # Resolve data_dir (expand ~ and relative paths)
    data_dir = config_data.get("storage", {}).get("data_dir", "~/memento_data")
    data_dir_path = Path(data_dir).expanduser()
    if not data_dir_path.is_absolute():
        data_dir_path = project_root / data_dir_path

    config_data.setdefault("storage", {})["data_dir"] = str(data_dir_path)

    # Load DB config and merge (DB overrides YAML)
    db_path = data_dir_path / "memento.db"
    db_config = _load_db_config(db_path)
    config_data = _merge_dicts(config_data, db_config)

    return Settings(**config_data)
