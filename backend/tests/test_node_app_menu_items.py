# backend/tests/test_node_app_menu_items.py
import importlib.util
import io
import sys
from pathlib import Path


def _load_menu_module():
    path = Path(__file__).resolve().parents[2] / "services" / "node" / "node_app" / "menu.py"
    # Always re-exec so edits are picked up without stale sys.modules
    name = "node_menu"
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_main_menu_labels():
    mod = _load_menu_module()
    labels = mod.MAIN_MENU_ITEMS
    assert len(labels) == 6
    assert "一键部署并启动" not in "".join(labels)
    assert any("查看状态" in x for x in labels)
    assert any("部署环境（修环境" in x for x in labels)
    assert any("卸载模型" in x for x in labels)
    assert any("冷启动" in x for x in labels)
    assert any("热启动" in x for x in labels)
    assert any("退出" in x for x in labels)


def test_interpret_csi_or_ss3_arrows():
    mod = _load_menu_module()
    interpret = mod._interpret_csi_or_ss3
    assert interpret("[A") == "up"
    assert interpret("OA") == "up"
    assert interpret("[B") == "down"
    assert interpret("OB") == "down"
    assert interpret("[C") == "right"
    assert interpret("OC") == "right"
    assert interpret("[D") == "left"
    assert interpret("OD") == "left"
    # Modified CSI (shift/alt/ctrl modifiers) — final letter still A/B/C/D
    assert interpret("[1;2A") == "up"
    assert interpret("[1;5B") == "down"
    assert interpret("[1;3C") == "right"
    assert interpret("[1;5D") == "left"


def test_interpret_csi_or_ss3_unknown_is_other_not_esc():
    mod = _load_menu_module()
    interpret = mod._interpret_csi_or_ss3
    # Only empty follow-up after ESC timeout = real Escape
    assert interpret("") == "esc"
    assert interpret("foo") == "other"
    assert interpret("[Z") == "other"
    assert interpret("[3~") == "other"
    assert interpret("OX") == "other"


def test_multi_help_text_contains_cancel_deploy(monkeypatch, capsys):
    """Multi-select help line should say ESC 取消本次部署 by default."""
    mod = _load_menu_module()
    monkeypatch.setattr(mod.sys, "stdout", io.StringIO())
    mod._render_menu("t", ["a"], 0, multi=True, checked=[False])
    out = mod.sys.stdout.getvalue()
    assert "ESC 取消本次部署" in out
    assert "取消整步" not in out


def test_multi_help_text_honors_custom_cancel_label(monkeypatch):
    """cancel_label kwarg should override the default ESC label."""
    mod = _load_menu_module()
    monkeypatch.setattr(mod.sys, "stdout", io.StringIO())
    mod._render_menu(
        "t", ["a"], 0, multi=True, checked=[False], cancel_label="取消卸载"
    )
    out = mod.sys.stdout.getvalue()
    assert "ESC 取消卸载" in out
    assert "取消本次部署" not in out


def test_multi_help_text_renders_hint(monkeypatch):
    """When hint is provided it should appear in the rendered menu."""
    mod = _load_menu_module()
    monkeypatch.setattr(mod.sys, "stdout", io.StringIO())
    mod._render_menu(
        "t", ["a"], 0, multi=True, checked=[False], hint="全不选则跳过"
    )
    out = mod.sys.stdout.getvalue()
    assert "全不选则跳过" in out


def test_select_many_esc_returns_none(monkeypatch):
    """ESC cancels multi-select and returns None (not empty list)."""
    mod = _load_menu_module()
    keys = iter(["esc"])
    monkeypatch.setattr(mod, "_read_key_unix", lambda: next(keys))
    monkeypatch.setattr(mod, "_read_key_windows", lambda: next(keys))
    monkeypatch.setattr(mod.sys, "stdout", io.StringIO())
    result = mod.select_many("title", ["opt1", "opt2"])
    assert result is None


def test_select_many_ctrl_c_returns_none(monkeypatch):
    """Ctrl+C (KeyboardInterrupt from read_key) cancels multi-select."""
    mod = _load_menu_module()

    def boom():
        raise KeyboardInterrupt

    monkeypatch.setattr(mod, "_read_key_unix", boom)
    monkeypatch.setattr(mod, "_read_key_windows", boom)
    monkeypatch.setattr(mod.sys, "stdout", io.StringIO())
    result = mod.select_many("title", ["opt1"])
    assert result is None


def test_select_many_enter_empty_returns_empty_list(monkeypatch):
    """Enter with nothing checked confirms empty selection (not cancel)."""
    mod = _load_menu_module()
    keys = iter(["enter"])
    monkeypatch.setattr(mod, "_read_key_unix", lambda: next(keys))
    monkeypatch.setattr(mod, "_read_key_windows", lambda: next(keys))
    monkeypatch.setattr(mod.sys, "stdout", io.StringIO())
    result = mod.select_many("title", ["opt1", "opt2"])
    assert result == []


def test_select_many_space_then_enter_returns_indices(monkeypatch):
    """Space toggles then Enter returns checked indices."""
    mod = _load_menu_module()
    # space on index 0, down, space on index 1, enter → [0, 1]
    keys = iter(["space", "down", "space", "enter"])
    monkeypatch.setattr(mod, "_read_key_unix", lambda: next(keys))
    monkeypatch.setattr(mod, "_read_key_windows", lambda: next(keys))
    monkeypatch.setattr(mod.sys, "stdout", io.StringIO())
    result = mod.select_many("title", ["a", "b", "c"])
    assert result == [0, 1]
