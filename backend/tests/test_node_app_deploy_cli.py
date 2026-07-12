# backend/tests/test_node_app_deploy_cli.py
"""Unit tests for node_app/deploy.py orchestration (mocked subprocess)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

NODE_APP = Path(__file__).resolve().parents[2] / "services" / "node" / "node_app"


def _load_deploy():
    """Load deploy + deps under stable sys.modules names for ImportError fallbacks."""
    order = (
        ("node_app_paths", "paths.py"),
        ("node_app_device", "device.py"),
        ("node_app_toolchain", "toolchain.py"),
        ("node_app_menu", "menu.py"),
        ("node_app_models", "models.py"),
        ("node_app_deploy", "deploy.py"),
    )
    for name, file in order:
        if name in sys.modules:
            continue
        path = NODE_APP / file
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        assert spec.loader is not None
        spec.loader.exec_module(mod)
    return sys.modules["node_app_deploy"]


def _reload_deploy():
    """Force re-exec deploy so it rebinds imports (after dep modules already loaded)."""
    for name in list(sys.modules):
        if name in (
            "node_app_deploy",
            "node_app_menu",
            "node_app_models",
            "node_app_paths",
            "node_app_device",
            "node_app_toolchain",
        ):
            del sys.modules[name]
    return _load_deploy()


def _patch_common(monkeypatch, mod, *, device="cpu"):
    monkeypatch.setattr(mod, "detect_best_device", lambda: device)
    monkeypatch.setattr(
        mod, "check_asr_models",
        lambda: {m.slug: False for m in mod.ASR_MODELS},
    )
    monkeypatch.setattr(
        mod, "check_embedding_models",
        lambda: {m.slug: False for m in mod.EMBEDDING_MODELS},
    )
    monkeypatch.setattr(mod, "_detect_device_in_venv", lambda _d: device)


def test_noninteractive_empty_selection_only_env_only(monkeypatch, capsys):
    """Empty non-interactive selection: ASR+Embedding --env-only only, no model downloads."""
    mod = _reload_deploy()
    calls: list[list[str]] = []
    toolchain_calls = []

    _patch_common(monkeypatch, mod)
    monkeypatch.setattr(mod, "ensure_toolchain", lambda: toolchain_calls.append(1))

    def fake_run(cmd, check=True):  # noqa: ARG001
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    mod.cmd_deploy(asr_slugs=[], embedding_ids=[], interactive=False)

    out = capsys.readouterr().out
    assert "未选择任何模型。" in out
    assert "将只修复/安装运行环境" in out
    assert toolchain_calls == [1]
    assert calls, "expected at least env-only deploy invocations"
    asr_cmds = [c for c in calls if str(c[1]).endswith("asr/deploy.py") or str(c[1]).endswith("asr\\deploy.py")]
    emb_cmds = [
        c for c in calls
        if str(c[1]).endswith("embedding/deploy.py") or str(c[1]).endswith("embedding\\deploy.py")
    ]

    assert any("--env-only" in c for c in asr_cmds)
    assert any("--env-only" in c for c in emb_cmds)
    assert not any("--models" in c for c in calls)
    # Embedding model download path has --model without --env-only
    emb_download = [c for c in emb_cmds if "--env-only" not in c]
    assert emb_download == []


def test_noninteractive_missing_asr_slug_triggers_models(monkeypatch):
    """Selected missing ASR slug should produce a --models call."""
    mod = _reload_deploy()
    calls: list[list[str]] = []

    _patch_common(monkeypatch, mod)
    monkeypatch.setattr(mod, "ensure_toolchain", lambda: None)

    def fake_run(cmd, check=True):  # noqa: ARG001
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    mod.cmd_deploy(
        asr_slugs=["sensevoice-small"],
        embedding_ids=[],
        interactive=False,
    )

    models_cmds = [c for c in calls if "--models" in c]
    assert len(models_cmds) == 1
    idx = models_cmds[0].index("--models")
    assert "sensevoice-small" in models_cmds[0][idx + 1]
    assert any("--env-only" in c for c in calls)


def test_noninteractive_installed_asr_skips_models(monkeypatch):
    """Selected but already-installed ASR models should not re-download."""
    mod = _reload_deploy()
    calls: list[list[str]] = []

    monkeypatch.setattr(mod, "detect_best_device", lambda: "cpu")
    monkeypatch.setattr(mod, "ensure_toolchain", lambda: None)
    monkeypatch.setattr(
        mod, "check_asr_models",
        lambda: {m.slug: True for m in mod.ASR_MODELS},
    )
    monkeypatch.setattr(
        mod, "check_embedding_models",
        lambda: {m.slug: True for m in mod.EMBEDDING_MODELS},
    )
    monkeypatch.setattr(mod, "_detect_device_in_venv", lambda _d: "cpu")

    def fake_run(cmd, check=True):  # noqa: ARG001
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    mod.cmd_deploy(
        asr_slugs=["sensevoice-small"],
        embedding_ids=[],
        interactive=False,
    )

    assert not any("--models" in c for c in calls)
    assert any("--env-only" in c for c in calls)


def test_embedding_slug_normalizes_to_model_id(monkeypatch):
    """embedding_ids may be slug; CLI must receive model_id."""
    mod = _reload_deploy()
    calls: list[list[str]] = []

    monkeypatch.setattr(mod, "detect_best_device", lambda: "cpu")
    monkeypatch.setattr(mod, "ensure_toolchain", lambda: None)
    monkeypatch.setattr(
        mod, "check_asr_models",
        lambda: {m.slug: True for m in mod.ASR_MODELS},
    )
    monkeypatch.setattr(
        mod, "check_embedding_models",
        lambda: {m.slug: False for m in mod.EMBEDDING_MODELS},
    )
    monkeypatch.setattr(mod, "_detect_device_in_venv", lambda _d: "cpu")

    def fake_run(cmd, check=True):  # noqa: ARG001
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    mod.cmd_deploy(
        asr_slugs=[],
        embedding_ids=["bge-m3"],  # slug form
        interactive=False,
    )

    emb_download = [
        c for c in calls
        if ("embedding/deploy.py" in str(c[1]) or "embedding\\deploy.py" in str(c[1]))
        and "--env-only" not in c
    ]
    assert len(emb_download) == 1
    idx = emb_download[0].index("--model")
    assert emb_download[0][idx + 1] == "BAAI/bge-m3"


def test_interactive_asr_cancel_skips_toolchain(monkeypatch, capsys):
    """ESC on ASR selection cancels deploy; ensure_toolchain must not run."""
    mod = _reload_deploy()
    toolchain_calls = []
    run_calls = []

    _patch_common(monkeypatch, mod)
    monkeypatch.setattr(mod, "ensure_toolchain", lambda: toolchain_calls.append(1))
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: run_calls.append(1) or SimpleNamespace(returncode=0))
    monkeypatch.setattr(mod, "_select_asr_interactive", lambda: None)

    mod.cmd_deploy(interactive=True)

    out = capsys.readouterr().out
    assert "已取消部署。" in out
    assert toolchain_calls == []
    assert run_calls == []


def test_interactive_embedding_cancel_skips_toolchain(monkeypatch, capsys):
    """ESC on Embedding selection cancels; no toolchain/subprocess after ASR ok."""
    mod = _reload_deploy()
    toolchain_calls = []
    run_calls = []

    _patch_common(monkeypatch, mod)
    monkeypatch.setattr(mod, "ensure_toolchain", lambda: toolchain_calls.append(1))
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: run_calls.append(1) or SimpleNamespace(returncode=0))
    monkeypatch.setattr(mod, "_select_asr_interactive", lambda: [])
    monkeypatch.setattr(mod, "_select_embedding_interactive", lambda: None)

    mod.cmd_deploy(interactive=True)

    out = capsys.readouterr().out
    assert "已取消部署。" in out
    assert toolchain_calls == []
    assert run_calls == []


def test_interactive_skip_both_env_only(monkeypatch, capsys):
    """Skip both menus (empty lists) still runs toolchain + env-only, no model downloads."""
    mod = _reload_deploy()
    calls: list[list[str]] = []
    toolchain_calls = []

    _patch_common(monkeypatch, mod)
    monkeypatch.setattr(mod, "ensure_toolchain", lambda: toolchain_calls.append(1))
    monkeypatch.setattr(mod, "_select_asr_interactive", lambda: [])
    monkeypatch.setattr(mod, "_select_embedding_interactive", lambda: [])

    def fake_run(cmd, check=True):  # noqa: ARG001
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    mod.cmd_deploy(interactive=True)

    out = capsys.readouterr().out
    assert "未选择任何模型。" in out
    assert "将只修复/安装运行环境" in out
    assert "已取消部署。" not in out
    assert toolchain_calls == [1]
    assert any("--env-only" in c for c in calls)
    assert not any("--models" in c for c in calls)
    emb_download = [
        c for c in calls
        if ("embedding/deploy.py" in str(c[1]) or "embedding\\deploy.py" in str(c[1]))
        and "--env-only" not in c
    ]
    assert emb_download == []


def test_select_asr_interactive_models_only(monkeypatch):
    """Checked model indices map to slugs."""
    mod = _reload_deploy()
    monkeypatch.setattr(mod, "select_many", lambda title, options, preselected=None, **kw: [0])  # noqa: ARG001
    monkeypatch.setattr(
        mod, "check_asr_models",
        lambda: {m.slug: False for m in mod.ASR_MODELS},
    )
    result = mod._select_asr_interactive()
    assert result == [mod.ASR_MODELS[0].slug]


def test_select_asr_interactive_cancel(monkeypatch):
    """select_many None propagates as cancel."""
    mod = _reload_deploy()
    monkeypatch.setattr(mod, "select_many", lambda title, options, preselected=None, **kw: None)  # noqa: ARG001
    monkeypatch.setattr(
        mod, "check_asr_models",
        lambda: {m.slug: False for m in mod.ASR_MODELS},
    )
    assert mod._select_asr_interactive() is None


def test_select_embedding_interactive_cancel(monkeypatch):
    mod = _reload_deploy()
    monkeypatch.setattr(mod, "select_many", lambda title, options, preselected=None, **kw: None)  # noqa: ARG001
    monkeypatch.setattr(
        mod, "check_embedding_models",
        lambda: {m.slug: False for m in mod.EMBEDDING_MODELS},
    )
    assert mod._select_embedding_interactive() is None


def test_select_menus_no_skip_label_and_hint_passed(monkeypatch):
    """Options passed to select_many must NOT contain any 跳过 row; hint must be threaded."""
    mod = _reload_deploy()
    seen: list[tuple[str, list[str], str | None]] = []

    def capture(title, options, preselected=None, cancel_label="取消本次部署", hint=None):  # noqa: ARG001
        seen.append((title, list(options), hint))
        return []  # confirm empty

    monkeypatch.setattr(mod, "select_many", capture)
    monkeypatch.setattr(
        mod, "check_asr_models",
        lambda: {m.slug: False for m in mod.ASR_MODELS},
    )
    monkeypatch.setattr(
        mod, "check_embedding_models",
        lambda: {m.slug: False for m in mod.EMBEDDING_MODELS},
    )

    assert mod._select_asr_interactive() == []
    assert mod._select_embedding_interactive() == []

    asr_title, asr_opts, asr_hint = seen[0]
    emb_title, emb_opts, emb_hint = seen[1]
    assert asr_title == "Select ASR models to install"
    assert emb_title == "Select Embedding models to install"
    # No skip option is appended anymore
    assert not any("跳过" in opt for opt in asr_opts)
    assert not any("跳过" in opt for opt in emb_opts)
    assert len(asr_opts) == len(mod.ASR_MODELS)
    assert len(emb_opts) == len(mod.EMBEDDING_MODELS)
    # Hint guidance is threaded through
    assert asr_hint == "全不选则跳过安装 ASR 模型"
    assert emb_hint == "全不选则跳过安装 Embedding 模型"


def test_interactive_selection_before_toolchain(monkeypatch):
    """Interactive path: selection happens before ensure_toolchain."""
    mod = _reload_deploy()
    order: list[str] = []

    _patch_common(monkeypatch, mod)

    def select_asr():
        order.append("asr")
        return []

    def select_emb():
        order.append("emb")
        return []

    def toolchain():
        order.append("toolchain")

    monkeypatch.setattr(mod, "_select_asr_interactive", select_asr)
    monkeypatch.setattr(mod, "_select_embedding_interactive", select_emb)
    monkeypatch.setattr(mod, "ensure_toolchain", toolchain)
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0))

    mod.cmd_deploy(interactive=True)

    assert order == ["asr", "emb", "toolchain"]
