#!/usr/bin/env python3
"""Deploy the Memento embedding service: venv, deps, torch, model download."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

SERVICE_DIR = Path(__file__).resolve().parent
VENV_DIR = SERVICE_DIR / ".venv"
MODELS_DIR = SERVICE_DIR / "models"
CUDA_TORCH_INDEX_URL = "https://download.pytorch.org/whl/cu121"
DEFAULT_MODEL = "all-MiniLM-L6-v2"

ProgressCallback = Callable[[str, str, int | None], None]


def python_bin() -> Path:
    """Return the venv python binary path."""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run_command(args: list[str | Path], cwd: Path | None = None) -> None:
    """Run a command via subprocess, raising on non-zero exit."""
    subprocess.run([str(a) for a in args], cwd=cwd, check=True)


def detect_best_device() -> str:
    """Detect the best available torch device: cuda > mps > cpu.

    Probes via the service venv python (which has torch), not the running
    python, since deploy.py may run under system python without torch.
    """
    script = (
        "import torch;"
        " print('cuda' if torch.cuda.is_available()"
        " else 'mps' if torch.backends.mps.is_available()"
        " else 'cpu')"
    )
    try:
        result = subprocess.run(
            [str(python_bin()), "-c", script],
            capture_output=True, text=True, timeout=30,
        )
        device = result.stdout.strip()
        if device in ("cuda", "mps", "cpu"):
            return device
    except Exception:
        pass
    return "cpu"


def _progress(
    on_progress: ProgressCallback | None,
    stage: str,
    detail: str,
    percent: int | None = None,
) -> None:
    if on_progress:
        on_progress(stage, detail, percent)


def ensure_environment(
    *,
    device: str = "cpu",
    on_progress: ProgressCallback | None = None,
) -> None:
    """Create venv if missing, install deps + torch."""
    created_venv = False
    try:
        if not VENV_DIR.is_dir():
            _progress(on_progress, "venv", "Creating virtual environment", 0)
            run_command([sys.executable, "-m", "venv", str(VENV_DIR)])
            created_venv = True

        _progress(on_progress, "venv", "Upgrading pip/setuptools/wheel", 10)
        run_command([
            str(python_bin()), "-m", "pip", "install",
            "--upgrade", "pip", "setuptools", "wheel",
        ])

        _progress(on_progress, "deps", "Installing Python dependencies", 20)
        run_command([
            str(python_bin()), "-m", "pip", "install",
            "-r", str(SERVICE_DIR / "requirements.txt"),
        ])

        _progress(on_progress, "torch", f"Installing torch (device={device})", 35)
        torch_cmd = [
            str(python_bin()), "-m", "pip", "install", "torch",
        ]
        if device == "cuda":
            torch_cmd.extend(["--index-url", CUDA_TORCH_INDEX_URL])
        run_command(torch_cmd)
    except Exception:
        if created_venv and VENV_DIR.is_dir():
            shutil.rmtree(VENV_DIR)
        raise


def download_model(model_id: str = DEFAULT_MODEL) -> None:
    """Download the embedding model to the local sentence-transformers cache."""
    script = (
        f"from sentence_transformers import SentenceTransformer; "
        f"SentenceTransformer('{model_id}', cache_folder='{MODELS_DIR}')"
    )
    run_command([str(python_bin()), "-c", script])


def deploy(
    *,
    device: str | None = None,
    model_id: str = DEFAULT_MODEL,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Full deploy: venv + deps + torch + model download."""
    if device is None:
        device = detect_best_device()
    _progress(on_progress, "env", f"Deploying embedding environment (device={device})", 0)
    ensure_environment(device=device, on_progress=on_progress)
    _progress(on_progress, "model", f"Downloading model {model_id}", 50)
    download_model(model_id)
    _progress(on_progress, "done", f"Embedding environment ready (device={device})", 100)


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy Memento Embedding service")
    parser.add_argument(
        "--device", choices=["cpu", "cuda", "mps", "auto"], default="auto",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    device = detect_best_device() if args.device == "auto" else args.device
    deploy(
        device=device,
        model_id=args.model,
        on_progress=lambda stage, detail, percent=None: print(f"{stage}: {detail}"),
    )


if __name__ == "__main__":
    main()