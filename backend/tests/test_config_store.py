"""Tests for local config persistence."""

from pathlib import Path

import yaml

from core.config_store import ConfigStore


def test_update_models_creates_file(tmp_path: Path):
    store = ConfigStore(tmp_path / "config.local.yaml")

    store.update_models(
        {"chat": {"provider": "cloud", "api_key": "sk-new", "model": "deepseek-chat"}}
    )

    data = yaml.safe_load((tmp_path / "config.local.yaml").read_text())
    assert data["models"]["chat"]["api_key"] == "sk-new"


def test_update_models_merges_preserving_other_sections(tmp_path: Path):
    config_path = tmp_path / "config.local.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "storage": {"keep_videos": True},
                "models": {"chat": {"api_key": "sk-old", "model": "m1"}},
            }
        )
    )
    store = ConfigStore(config_path)

    store.update_models({"chat": {"model": "m2"}})

    data = yaml.safe_load(config_path.read_text())
    assert data["storage"]["keep_videos"] is True  # untouched section
    assert data["models"]["chat"]["api_key"] == "sk-old"  # merged, not replaced
    assert data["models"]["chat"]["model"] == "m2"


def test_update_models_ignores_none_values(tmp_path: Path):
    config_path = tmp_path / "config.local.yaml"
    config_path.write_text(
        yaml.safe_dump({"models": {"chat": {"api_key": "sk-old"}}})
    )
    store = ConfigStore(config_path)

    store.update_models({"chat": {"api_key": None, "model": "m2"}})

    data = yaml.safe_load(config_path.read_text())
    assert data["models"]["chat"]["api_key"] == "sk-old"
