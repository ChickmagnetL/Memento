from __future__ import annotations

import os
import sys

MAIN_MENU_ITEMS = [
    "查看状态",
    "部署环境（修环境 + 可选装模型）",
    "卸载模型",
    "冷启动服务",
    "热启动服务",
    "退出",
]


def _render_menu(
    title: str,
    options: list[str],
    selected: int,
    *,
    multi: bool = False,
    checked: list[bool] | None = None,
    cancel_label: str = "取消本次部署",
    hint: str | None = None,
) -> None:
    """Clear screen and draw the menu, highlighting the selected line."""
    sys.stdout.write("\033[2J\033[H")  # clear screen + cursor home
    sys.stdout.write(f"{title}\n\n")
    for i, opt in enumerate(options):
        if multi and checked is not None:
            mark = "[x]" if checked[i] else "[ ]"
            body = f"{mark} {opt}"
        else:
            body = opt
        if i == selected:
            sys.stdout.write(f"\033[7m> {body}\033[0m\n")  # inverted video
        else:
            sys.stdout.write(f"  {body}\n")
    if multi:
        sys.stdout.write("\n")
        if hint is not None:
            sys.stdout.write(f"{hint}\n")
        sys.stdout.write(f"(↑/↓ 移动，Space 勾选，Enter 确认，ESC {cancel_label})\n")
    else:
        sys.stdout.write("\n(↑/↓ 选择，Enter 确认，Ctrl+C 退出)\n")
    sys.stdout.flush()


def _interpret_csi_or_ss3(seq: str) -> str:
    if not seq:
        return "esc"  # lone ESC only
    if seq[0] == "O" and len(seq) >= 2:
        final = seq[1]
        if final == "A": return "up"
        if final == "B": return "down"
        if final == "C": return "right"
        if final == "D": return "left"
        return "other"
    if seq[0] == "[":
        final = seq[-1]
        if final == "A": return "up"
        if final == "B": return "down"
        if final == "C": return "right"
        if final == "D": return "left"
        return "other"
    return "other"


def _read_key_unix() -> str:
    """Read one logical key on Unix (termios/tty + select for ESC disambiguation)."""
    import select
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        raw = os.read(fd, 1)
        if not raw:
            return "other"
        ch = raw.decode("utf-8", errors="ignore")
        if ch == "\x1b":  # ESC — CSI ([A) or SS3 (OA) arrow sequences
            seq = ""
            timeout = 0.15  # first follow-up: distinguish lone ESC
            while len(seq) < 8:
                ready, _, _ = select.select([fd], [], [], timeout)
                if not ready:
                    break
                nxt_raw = os.read(fd, 1)
                if not nxt_raw:
                    break
                nxt = nxt_raw.decode("utf-8", errors="ignore")
                if not nxt:
                    break
                seq += nxt
                timeout = 0.03  # subsequent inter-byte timeout
                # Complete SS3: O + letter
                if len(seq) >= 2 and seq[0] == "O" and seq[1].isalpha():
                    break
                # Complete CSI: [ ... ending with letter or ~
                if seq[0] == "[" and len(seq) >= 2 and (seq[-1].isalpha() or seq[-1] == "~"):
                    break
            return _interpret_csi_or_ss3(seq)
        if ch in ("\r", "\n"):
            return "enter"
        if ch == " ":
            return "space"
        if ch == "\x03":  # Ctrl-C
            raise KeyboardInterrupt
        return "other"
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _read_key_windows() -> str:
    """Read one logical key on Windows (msvcrt)."""
    import msvcrt
    ch = msvcrt.getch()
    if ch in (b"\x00", b"\xe0"):  # special-key prefix (arrows, etc.)
        ch2 = msvcrt.getch()
        if ch2 == b"H":
            return "up"
        if ch2 == b"P":
            return "down"
        if ch2 == b"K":
            return "left"
        if ch2 == b"M":
            return "right"
        return "other"
    if ch == b"\x1b":  # ESC
        return "esc"
    if ch in (b"\r", b"\n"):
        return "enter"
    if ch == b" ":
        return "space"
    if ch == b"\x03":  # Ctrl-C
        raise KeyboardInterrupt
    return "other"


def select_one(title: str, options: list[str]) -> int:
    """Arrow keys + Enter. Returns index or -1 if cancel."""
    read_key = _read_key_windows if sys.platform == "win32" else _read_key_unix
    selected = 0
    _render_menu(title, options, selected)
    try:
        while True:
            key = read_key()
            if key == "up":
                selected = (selected - 1) % len(options)
            elif key == "down":
                selected = (selected + 1) % len(options)
            elif key == "enter":
                sys.stdout.write("\033[0m\n")
                sys.stdout.flush()
                return selected
            elif key == "esc":
                sys.stdout.write("\n")
                return -1
            _render_menu(title, options, selected)
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        return -1


def select_many(
    title: str,
    options: list[str],
    preselected: list[bool] | None = None,
    cancel_label: str = "取消本次部署",
    hint: str | None = None,
) -> list[int] | None:
    """Space toggles selection, Enter confirms (list of indices, may be empty).

    ESC / Ctrl+C cancel the whole deploy and return None.
    """
    read_key = _read_key_windows if sys.platform == "win32" else _read_key_unix
    selected = 0
    checked = list(preselected) if preselected is not None else [False] * len(options)
    _render_menu(title, options, selected, multi=True, checked=checked, cancel_label=cancel_label, hint=hint)
    try:
        while True:
            key = read_key()
            if key == "up":
                selected = (selected - 1) % len(options)
            elif key == "down":
                selected = (selected + 1) % len(options)
            elif key == "space":
                checked[selected] = not checked[selected]
            elif key == "enter":
                sys.stdout.write("\033[0m\n")
                sys.stdout.flush()
                return [i for i, on in enumerate(checked) if on]
            elif key == "esc":
                sys.stdout.write("\n")
                return None
            _render_menu(title, options, selected, multi=True, checked=checked, cancel_label=cancel_label, hint=hint)
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        return None
