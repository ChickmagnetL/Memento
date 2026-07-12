from __future__ import annotations

import os
import sys

try:
    from .diag import cmd_probe
    from .deploy import cmd_deploy
    from .serve import cmd_serve
    from .manage import cmd_uninstall_models
    from .menu import MAIN_MENU_ITEMS, select_one
except ImportError:
    from node_app_diag import cmd_probe  # type: ignore
    from node_app_deploy import cmd_deploy  # type: ignore
    from node_app_serve import cmd_serve  # type: ignore
    from node_app_manage import cmd_uninstall_models  # type: ignore
    from node_app_menu import MAIN_MENU_ITEMS, select_one  # type: ignore


def _parse_csv_flag(argv: list[str], name: str) -> list[str] | None:
    """Return list if --name VALUE present, else None."""
    flag = f"--{name}"
    if flag not in argv:
        return None
    i = argv.index(flag)
    if i + 1 >= len(argv) or argv[i + 1].startswith("--"):
        return []
    return [p.strip() for p in argv[i + 1].split(",") if p.strip()]


def _interactive() -> None:
    """Run the interactive menu loop."""
    while True:
        choice = select_one("Memento 远程节点", MAIN_MENU_ITEMS)
        if choice in (-1, 5):  # cancelled or "退出"
            print("Bye.")
            return
        if choice == 0:
            cmd_probe()
            try:
                input("\n按 Enter 返回菜单...")
            except KeyboardInterrupt:
                print("\nBye.")
                return
        elif choice == 1:
            cmd_deploy(interactive=True)
            try:
                input("\n按 Enter 返回菜单...")
            except KeyboardInterrupt:
                print("\nBye.")
                return
        elif choice == 2:
            cmd_uninstall_models()
            try:
                input("\n按 Enter 返回菜单...")
            except KeyboardInterrupt:
                print("\nBye.")
                return
        elif choice == 3:
            cmd_serve(warm=False)
        elif choice == 4:
            cmd_serve(warm=True)


def main(argv: list[str] | None = None) -> None:
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        _interactive()
        return
    cmd = argv[0]
    if cmd == "probe":
        cmd_probe()
        return
    if cmd == "deploy":
        asr = _parse_csv_flag(argv, "asr")
        emb = _parse_csv_flag(argv, "embedding")
        has_flags = asr is not None or emb is not None
        interactive = sys.stdin.isatty() and not has_flags
        cmd_deploy(
            asr_slugs=asr or [],
            embedding_ids=emb or [],
            interactive=interactive,
        )
        return
    if cmd == "serve":
        cmd_serve(warm=("--warm" in argv))
        return
    print(f"Unknown command: {cmd}")
    print("Usage: bootstrap.py [probe|deploy|serve] ...")
    sys.exit(2)
