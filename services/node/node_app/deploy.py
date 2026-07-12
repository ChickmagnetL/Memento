"""Interactive / non-interactive deploy orchestration for ASR + Embedding services."""

from __future__ import annotations

import subprocess
import sys

try:
    from .paths import ASR_DIR, EMBEDDING_DIR
    from .device import detect_best_device, _detect_device_in_venv
    from .toolchain import ensure_toolchain
    from .menu import select_many
    from .models import (
        ASR_MODELS,
        EMBEDDING_MODELS,
        check_asr_models,
        check_embedding_models,
    )
except ImportError:
    from node_app_paths import ASR_DIR, EMBEDDING_DIR  # type: ignore
    from node_app_device import detect_best_device, _detect_device_in_venv  # type: ignore
    from node_app_toolchain import ensure_toolchain  # type: ignore
    from node_app_menu import select_many  # type: ignore
    from node_app_models import (  # type: ignore
        ASR_MODELS,
        EMBEDDING_MODELS,
        check_asr_models,
        check_embedding_models,
    )


def _run(cmd: list[str]) -> None:
    """Print and run a subprocess command; raise on non-zero exit."""
    print(f"  $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def _select_asr_interactive() -> list[str] | None:
    """Multi-select ASR models; None = cancelled, [] = skip/none, else slugs."""
    status = check_asr_models()
    options = [
        f"[{'INSTALLED' if status.get(m.slug) else 'MISSING'}] "
        f"{m.label} ({m.slug}, {m.size})"
        for m in ASR_MODELS
    ]
    indices = select_many(
        "Select ASR models to install",
        options,
        hint="全不选则跳过安装 ASR 模型",
    )
    if indices is None:
        return None
    return [ASR_MODELS[i].slug for i in indices]


def _select_embedding_interactive() -> list[str] | None:
    """Multi-select embedding models; None = cancelled, [] = skip/none, else model_ids."""
    status = check_embedding_models()
    options = [
        f"[{'INSTALLED' if status.get(m.slug) else 'MISSING'}] "
        f"{m.label} ({m.slug})"
        for m in EMBEDDING_MODELS
    ]
    indices = select_many(
        "Select Embedding models to install",
        options,
        hint="全不选则跳过安装 Embedding 模型",
    )
    if indices is None:
        return None
    return [EMBEDDING_MODELS[i].model_id for i in indices]


def _normalize_embedding_ids(values: list[str]) -> list[str]:
    """Accept slug or model_id; return model_ids. Unknown values pass through."""
    by_slug = {m.slug: m.model_id for m in EMBEDDING_MODELS}
    by_id = {m.model_id: m.model_id for m in EMBEDDING_MODELS}
    out: list[str] = []
    for v in values:
        if v in by_id:
            out.append(by_id[v])
        elif v in by_slug:
            out.append(by_slug[v])
        else:
            out.append(v)
    return out


def _deploy_asr(device: str, slugs: list[str]) -> None:
    """Always ensure ASR env; install only selected missing slugs."""
    _run([
        sys.executable, str(ASR_DIR / "deploy.py"),
        "--device", device, "--env-only",
    ])
    if not slugs:
        return
    status = check_asr_models()
    missing = [s for s in slugs if not status.get(s, False)]
    if not missing:
        print("  ASR: selected models already installed; skipping download.")
        return
    _run([
        sys.executable, str(ASR_DIR / "deploy.py"),
        "--device", device, "--models", ",".join(missing),
    ])


def _deploy_embedding(device: str, model_ids: list[str]) -> None:
    """Always ensure Embedding env; download each selected missing model_id."""
    _run([
        sys.executable, str(EMBEDDING_DIR / "deploy.py"),
        "--device", device, "--env-only",
    ])
    if not model_ids:
        return
    # Map model_id → slug for status lookup
    id_to_slug = {m.model_id: m.slug for m in EMBEDDING_MODELS}
    status = check_embedding_models()
    for mid in model_ids:
        slug = id_to_slug.get(mid, mid)
        if status.get(slug, False):
            print(f"  Embedding: {mid} already installed; skipping download.")
            continue
        _run([
            sys.executable, str(EMBEDDING_DIR / "deploy.py"),
            "--device", device, "--model", mid,
        ])


def _print_final_status(device: str) -> None:
    """Print model install status and per-venv torch device (with CUDA warnings)."""
    print()
    print("Deploy complete.")
    print()
    print("Final status:")
    print("  ASR models:")
    for model_id, present in check_asr_models().items():
        status = "INSTALLED" if present else "MISSING"
        print(f"    [{status}] {model_id}")
    print("  Embedding models:")
    for model_id, present in check_embedding_models().items():
        status = "INSTALLED" if present else "MISSING"
        print(f"    [{status}] {model_id}")
    asr_torch = _detect_device_in_venv(ASR_DIR)
    emb_torch = _detect_device_in_venv(EMBEDDING_DIR)
    print(f"  ASR venv torch device:       {asr_torch}")
    print(f"  Embedding venv torch device: {emb_torch}")
    if device == "cuda":
        if asr_torch != "cuda":
            print("  WARNING: host has nvidia-smi but ASR venv torch has no CUDA.")
        if emb_torch != "cuda":
            print("  WARNING: host has nvidia-smi but Embedding venv torch has no CUDA.")


def cmd_deploy(
    *,
    asr_slugs: list[str] | None = None,
    embedding_ids: list[str] | None = None,
    interactive: bool = True,
) -> None:
    """Detect device, select models (interactive), ensure toolchain, deploy ASR + Embedding.

    interactive=True: multi-select menus for ASR then Embedding (before toolchain).
      ESC / Ctrl+C on either menu cancels the whole deploy (no toolchain, no env).
      Empty selection on a menu skips model install for that step.
    interactive=False: use provided asr_slugs / embedding_ids (None → empty); toolchain first.
    Empty selection on both sides: env-only (no model downloads).
    """
    device = detect_best_device()
    print(f"Detected device: {device}")
    print()

    if interactive:
        asr_slugs = _select_asr_interactive()
        if asr_slugs is None:
            print("已取消部署。")
            return
        embedding_ids = _select_embedding_interactive()
        if embedding_ids is None:
            print("已取消部署。")
            return
    else:
        asr_slugs = list(asr_slugs or [])
        embedding_ids = _normalize_embedding_ids(list(embedding_ids or []))

    print("Preparing isolated toolchain (uv + Python 3.12 + venvs)...")
    ensure_toolchain()
    print()

    if not asr_slugs and not embedding_ids:
        print("未选择任何模型。")
        print("将只修复/安装运行环境（venv、依赖、torch），不会下载模型。")
        print()

    print()
    if asr_slugs:
        print(f"ASR: ensuring environment + installing selected ({', '.join(asr_slugs)})...")
    else:
        print("ASR: ensuring environment only (no models selected)...")
    _deploy_asr(device, asr_slugs)

    print()
    if embedding_ids:
        print(
            f"Embedding: ensuring environment + installing selected "
            f"({', '.join(embedding_ids)})..."
        )
    else:
        print("Embedding: ensuring environment only (no models selected)...")
    _deploy_embedding(device, embedding_ids)

    _print_final_status(device)
