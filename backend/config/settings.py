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

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


# ============================================================
# SECTION 1: Model Configuration
# ============================================================

class ModelConfig(BaseModel):
    """Configuration for a model service (ASR/Embedding/Chat)."""

    provider: Literal["local", "ollama", "openai", "cloud"] = "cloud"
    endpoint: str | None = None
    api_key: str | None = None
    model: str | None = None


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
    def load_from_yaml(cls, config_path: Path | str) -> "Settings":
        """
        Load settings from YAML file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            Settings instance with loaded configuration
        """
        config_path = Path(config_path)

        if not config_path.exists():
            return cls()

        with open(config_path) as f:
            config_data = yaml.safe_load(f) or {}

        return cls(**config_data)


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
    backend_dir = Path(__file__).parent.parent
    project_root = backend_dir.parent

    # Start with defaults
    default_config = backend_dir / "config" / "default.yaml"
    settings = Settings.load_from_yaml(default_config)

    # Load user config if exists
    user_config = project_root / "config.yaml"
    if user_config.exists():
        settings = Settings.load_from_yaml(user_config)

    # Load local overrides if exists
    local_config = project_root / "config.local.yaml"
    if local_config.exists():
        user_settings = Settings.load_from_yaml(user_config) if user_config.exists() else Settings()
        local_settings = Settings.load_from_yaml(local_config)
        # Merge: local overrides user
        settings = Settings.model_validate({
            **user_settings.model_dump(),
            **local_settings.model_dump()
        })

    return settings
