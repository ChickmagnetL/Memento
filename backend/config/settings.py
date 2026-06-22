"""
Configuration management for Memento backend.

This module loads configuration from YAML files and environment variables.
Settings are validated using Pydantic models.

Priority (highest to lowest):
1. Environment variables
2. config.local.yaml (git-ignored, for local overrides)
3. config.yaml (user configuration)
4. default.yaml (default configuration)

Author: Memento Team
Last Updated: 2026-06-07
"""

import os
import sys
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource


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

def get_settings() -> Settings:
    """
    Get application settings with layered configuration.

    Load order (later overrides earlier):
    1. default.yaml
    2. ../config.yaml (user config)
    3. ../config.local.yaml (local overrides, git-ignored)
    4. Environment variables

    Returns:
        Settings instance
    """
    backend_dir = resolve_backend_dir()
    project_root = resolve_project_root(backend_dir)

    default_config = backend_dir / "config" / "default.yaml"
    user_config = project_root / "config.yaml"
    local_config = project_root / "config.local.yaml"
    config_data = _merge_dicts(_load_yaml_data(default_config), _load_yaml_data(user_config))
    config_data = _merge_dicts(config_data, _load_yaml_data(local_config))

    data_dir = config_data.get("storage", {}).get("data_dir")
    if data_dir and not Path(data_dir).is_absolute():
        config_data.setdefault("storage", {})["data_dir"] = str(project_root / data_dir)

    return Settings(**config_data)
