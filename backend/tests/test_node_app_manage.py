# backend/tests/test_node_app_manage.py
"""Unit tests for node_app/manage.py and model uninstall helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

NODE_APP = Path(__file__).resolve().parents[2] / "services" / "node" / "node_app"


def _load_manage():
    order = (
        ("node_app_paths", "paths.py"),
        ("node_app_device", "device.py"),
        ("node_app_menu", "menu.py"),
        ("node_app_models", "models.py"),
        ("node_app_manage", "manage.py"),
    )
    for name in list(sys.modules):
        if name in {n for n, _ in order}:
            del sys.modules[name]
    for name, file in order:
        path = NODE_APP / file
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        assert spec.loader is not None
        spec.loader.exec_module(mod)
    return sys.modules["node_app_manage"]


def test_return_from_family_menu(monkeypatch, capsys):
    mod = _load_manage()
    monkeypatch.setattr(mod, "select_one", lambda title, options: 2)  # 返回
    mod.cmd_uninstall_models()
    # No crash, no deploy messages
    out = capsys.readouterr().out
    assert "请先运行" not in out


def test_uninstall_asr_none_installed(monkeypatch, capsys):
    mod = _load_manage()
    choices = iter([0])  # ASR family only (no action step)
    monkeypatch.setattr(mod, "select_one", lambda title, options: next(choices))
    monkeypatch.setattr(
        mod, "check_asr_models",
        lambda: {m.slug: False for m in mod.ASR_MODELS},
    )
    mod.cmd_uninstall_models()
    out = capsys.readouterr().out
    assert "没有已安装的 ASR 模型" in out


def test_uninstall_embedding_flow(monkeypatch, capsys, tmp_path):
    mod = _load_manage()
    emb = tmp_path / "embedding"
    cache = emb / "models" / "models--BAAI--bge-m3"
    cache.mkdir(parents=True)
    (cache / "x").write_text("1", encoding="utf-8")

    # family=Embedding, confirm=确认
    ones = iter([1, 0])
    monkeypatch.setattr(mod, "select_one", lambda title, options: next(ones))
    monkeypatch.setattr(mod, "select_many", lambda title, options, preselected=None, **kw: [0])  # noqa: ARG001
    monkeypatch.setattr(
        mod, "check_embedding_models",
        lambda: {"bge-m3": True, "qwen3-embedding-0.6b": False},
    )

    # Route uninstall through real helper with emb_dir
    from node_app_models import uninstall_embedding_model as real_uninst

    def _uninst(slug, emb_dir=None):
        return real_uninst(slug, emb_dir or emb)

    monkeypatch.setattr(mod, "uninstall_embedding_model", _uninst)

    mod.cmd_uninstall_models()
    out = capsys.readouterr().out
    assert "已卸载 Embedding: bge-m3" in out
    assert not cache.exists()


def test_uninstall_asr_passes_cancel_uninstall_label(monkeypatch):
    """Uninstall multi-select must pass cancel_label='取消卸载'."""
    mod = _load_manage()
    captured: dict = {}

    def fake_select_many(title, options, preselected=None, cancel_label="取消本次部署", hint=None):  # noqa: ARG001
        captured["cancel_label"] = cancel_label
        return None  # cancel

    ones = iter([0])  # ASR family
    monkeypatch.setattr(mod, "select_one", lambda title, options: next(ones))
    monkeypatch.setattr(mod, "select_many", fake_select_many)
    monkeypatch.setattr(
        mod, "check_asr_models",
        lambda: {m.slug: True for m in mod.ASR_MODELS},
    )

    mod.cmd_uninstall_models()
    assert captured["cancel_label"] == "取消卸载"
