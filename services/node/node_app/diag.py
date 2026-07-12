from __future__ import annotations

try:
    from .device import detect_best_device, _detect_device_in_venv
    from .models import check_asr_models, check_embedding_models
    from .paths import ASR_DIR, EMBEDDING_DIR
except ImportError:
    from node_app_device import detect_best_device, _detect_device_in_venv  # type: ignore
    from node_app_models import check_asr_models, check_embedding_models  # type: ignore
    from node_app_paths import ASR_DIR, EMBEDDING_DIR  # type: ignore


def cmd_probe() -> None:
    """Print hardware, model status, and per-venv torch devices."""
    device = detect_best_device()
    print(f"Hardware: {device}")
    if device in ("cuda", "mps"):
        print(f"  Accelerated: YES ({device})")
    else:
        print("  Accelerated: NO (CPU only)")
        print("  Note: CUDA/MPS not detected. OpenVINO/RKNN not yet supported.")
        print("  See: docs/superpowers/specs/2026-07-09-v0.3.0-remote-asr-embedding-node-design.md")

    print()
    print("ASR models:")
    for model_id, present in check_asr_models().items():
        status = "INSTALLED" if present else "MISSING"
        print(f"  [{status}] {model_id}")

    print()
    print("Embedding models:")
    for model_id, present in check_embedding_models().items():
        status = "INSTALLED" if present else "MISSING"
        print(f"  [{status}] {model_id}")

    print()
    asr_torch = _detect_device_in_venv(ASR_DIR)
    emb_torch = _detect_device_in_venv(EMBEDDING_DIR)
    print(f"ASR venv torch device:       {asr_torch}")
    print(f"Embedding venv torch device: {emb_torch}")
    if device == "cuda":
        if asr_torch != "cuda":
            print("WARNING: host has nvidia-smi but ASR venv torch has no CUDA.")
        if emb_torch != "cuda":
            print("WARNING: host has nvidia-smi but Embedding venv torch has no CUDA.")
