"""Interactive uninstall of ASR and Embedding model caches."""

from __future__ import annotations

try:
    from .menu import select_many, select_one
    from .models import (
        ASR_MODELS,
        EMBEDDING_MODELS,
        check_asr_models,
        check_embedding_models,
        uninstall_asr_model,
        uninstall_embedding_model,
    )
except ImportError:
    from node_app_menu import select_many, select_one  # type: ignore
    from node_app_models import (  # type: ignore
        ASR_MODELS,
        EMBEDDING_MODELS,
        check_asr_models,
        check_embedding_models,
        uninstall_asr_model,
        uninstall_embedding_model,
    )


def _uninstall_asr_models() -> None:
    status = check_asr_models()
    installed = [m for m in ASR_MODELS if status.get(m.slug, False)]
    if not installed:
        print("当前没有已安装的 ASR 模型。")
        return

    options = [f"{m.label} ({m.slug})" for m in installed]
    indices = select_many("选择要卸载的 ASR 模型", options, cancel_label="取消卸载")
    if indices is None:
        print("已取消。")
        return
    if not indices:
        print("未选择任何模型。")
        return

    confirm = select_one("确认卸载所选 ASR 模型？", ["确认卸载", "取消"])
    if confirm != 0:
        print("已取消卸载。")
        return

    for i in indices:
        if i < 0 or i >= len(installed):
            continue
        slug = installed[i].slug
        ok = uninstall_asr_model(slug)
        if ok:
            print(f"  已卸载 ASR: {slug}")
        else:
            print(f"  未找到缓存，跳过: {slug}")


def _uninstall_embedding_models() -> None:
    status = check_embedding_models()
    installed = [m for m in EMBEDDING_MODELS if status.get(m.slug, False)]
    if not installed:
        print("当前没有已安装的 Embedding 模型。")
        return

    options = [f"{m.label} ({m.slug})" for m in installed]
    indices = select_many("选择要卸载的 Embedding 模型", options, cancel_label="取消卸载")
    if indices is None:
        print("已取消。")
        return
    if not indices:
        print("未选择任何模型。")
        return

    confirm = select_one("确认卸载所选 Embedding 模型？", ["确认卸载", "取消"])
    if confirm != 0:
        print("已取消卸载。")
        return

    for i in indices:
        if i < 0 or i >= len(installed):
            continue
        slug = installed[i].slug
        ok = uninstall_embedding_model(slug)
        if ok:
            print(f"  已卸载 Embedding: {slug}")
        else:
            print(f"  未找到缓存，跳过: {slug}")


def cmd_uninstall_models() -> None:
    """Interactive uninstall of ASR or Embedding model caches."""
    family = select_one(
        "卸载模型",
        ["卸载 ASR 模型", "卸载 Embedding 模型", "返回"],
    )
    if family in (-1, 2):
        return
    if family == 0:
        _uninstall_asr_models()
    else:
        _uninstall_embedding_models()
