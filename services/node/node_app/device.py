from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

try:
    from .paths import ASR_DIR
except ImportError:
    from node_app_paths import ASR_DIR  # type: ignore


def _venv_python(service_dir: Path) -> Path:
    """Return the venv python binary path, OS-correct."""
    if sys.platform == "win32":
        return service_dir / ".venv" / "Scripts" / "python.exe"
    return service_dir / ".venv" / "bin" / "python"


def _venv_uvicorn(service_dir: Path) -> Path:
    """Return the venv uvicorn binary path, OS-correct."""
    if sys.platform == "win32":
        return service_dir / ".venv" / "Scripts" / "uvicorn.exe"
    return service_dir / ".venv" / "bin" / "uvicorn"


def _detect_device_in_venv(service_dir: Path) -> str:
    """Probe that service's venv torch. If venv missing, fall back to nvidia-smi/mps/cpu."""
    venv_python = _venv_python(service_dir)
    if venv_python.exists():
        script = (
            "import torch;"
            " print('cuda' if torch.cuda.is_available()"
            " else 'mps' if torch.backends.mps.is_available()"
            " else 'cpu')"
        )
        try:
            result = subprocess.run(
                [str(venv_python), "-c", script],
                capture_output=True, text=True, timeout=30,
            )
            device = result.stdout.strip()
            if device in ("cuda", "mps", "cpu"):
                return device
        except Exception:
            pass
        return "cpu"
    # venv not built — hardware heuristic for first deploy
    if shutil.which("nvidia-smi") is not None:
        return "cuda"
    if sys.platform == "darwin":
        return "mps"
    return "cpu"


def detect_best_device() -> str:
    """Device for deploy/probe: hardware first so CUDA hosts always get CUDA torch install.

    Prefer nvidia-smi / platform over probing a sticky CPU torch already in the venv,
    so redeploy can force-install CUDA wheels.
    """
    if shutil.which("nvidia-smi") is not None:
        return "cuda"
    if sys.platform == "darwin":
        return "mps"
    # no obvious accel — probe ASR venv if present
    return _detect_device_in_venv(ASR_DIR)
