"""Tests for frozen-mode path resolution."""

from pathlib import Path

from config.settings import resolve_backend_dir


def test_resolve_backend_dir_normal_mode():
    """In normal mode it is the backend package directory."""
    assert (resolve_backend_dir() / "config").is_dir()


def test_resolve_backend_dir_frozen_mode(monkeypatch, tmp_path: Path):
    import sys

    bundle = tmp_path / "bundle"
    (bundle / "config").mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    assert resolve_backend_dir() == bundle
