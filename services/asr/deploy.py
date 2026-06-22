"""Deploy the standalone Memento ASR service environment."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable


SERVICE_DIR = Path(__file__).resolve().parent
VENV_DIR = SERVICE_DIR / ".venv"
CUDA_TORCH_INDEX_URL = "https://download.pytorch.org/whl/cu121"

ProgressCallback = Callable[[str, str, int | None], None]

# ---------------------------------------------------------------------------
# Moonshine spec → ModelArch mapping
# ---------------------------------------------------------------------------

_SPEC_TO_ARCH: dict[str, str] = {
    "tiny-en": "TINY",
    "base-en": "BASE",
    "tiny-streaming-en": "TINY_STREAMING",
    "small-streaming-en": "SMALL_STREAMING",
    "medium-streaming-en": "MEDIUM_STREAMING",
}


def python_bin() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run_command(args: list[str | Path], cwd: Path | None = None) -> None:
    subprocess.run(
        [str(arg) for arg in args],
        cwd=str(cwd or SERVICE_DIR),
        check=True,
    )


def has_nvidia_gpu() -> bool:
    return shutil.which("nvidia-smi") is not None


def torch_install_command(device: str | None = None) -> list[str]:
    use_cuda = device == "cuda" or (
        device is None and sys.platform in {"linux", "win32"} and has_nvidia_gpu()
    )
    command = [str(python_bin()), "-m", "pip", "install", "torch", "torchaudio"]
    if use_cuda:
        command.extend(["--index-url", CUDA_TORCH_INDEX_URL])
    return command


def _progress(
    on_progress: ProgressCallback | None,
    stage: str,
    detail: str,
    percent: int | None = None,
) -> None:
    if on_progress is not None:
        on_progress(stage, detail, percent)


# ---------------------------------------------------------------------------
# Environment setup (venv + deps + torch, NO model downloads)
# ---------------------------------------------------------------------------


def ensure_environment(
    *,
    device: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Create venv, install pip deps and torch.  Does NOT download models."""
    created_venv = False
    try:
        if not VENV_DIR.exists():
            _progress(on_progress, "venv", "Creating ASR virtual environment", 10)
            run_command([sys.executable, "-m", "venv", str(VENV_DIR)])
            created_venv = True

        python = python_bin()
        _progress(on_progress, "dependencies", "Installing ASR dependencies", 30)
        run_command(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--upgrade",
                "pip",
                "setuptools",
                "wheel",
            ]
        )
        run_command(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "-r",
                str(SERVICE_DIR / "requirements.txt"),
            ]
        )

        _progress(on_progress, "torch", "Installing platform torch wheel", 45)
        run_command(torch_install_command(device=device))

        _progress(on_progress, "environment", "ASR environment ready", 50)
    except Exception:
        if created_venv and VENV_DIR.exists():
            shutil.rmtree(VENV_DIR, ignore_errors=True)
        raise


# ---------------------------------------------------------------------------
# Model download
# ---------------------------------------------------------------------------


def download_model(
    python: Path,
    *,
    model_id: str,
    runtime: str,
    spec: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Download a single model by triggering its Python import."""
    label = model_id
    _progress(on_progress, "models", f"Downloading {label}", 50)

    if runtime == "sensevoice":
        run_command(
            [
                str(python),
                "-c",
                (
                    "from funasr import AutoModel; "
                    f"AutoModel(model='{model_id}', disable_update=True)"
                ),
            ]
        )
    elif runtime == "moonshine":
        if spec is None or spec not in _SPEC_TO_ARCH:
            raise ValueError(f"Unknown moonshine spec: {spec}")
        arch = _SPEC_TO_ARCH[spec]
        run_command(
            [
                str(python),
                "-c",
                (
                    "from moonshine_voice import ModelArch, get_model_for_language; "
                    f"get_model_for_language(wanted_language='en', wanted_model_arch=ModelArch.{arch})"
                ),
            ]
        )
    else:
        raise ValueError(f"Unknown runtime: {runtime}")

    _progress(on_progress, "models", f"Downloaded {label}", 100)


def download_models(
    python: Path,
    *,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Download ALL known models (backward-compat bulk path)."""
    _progress(on_progress, "models", "Downloading SenseVoiceSmall", 50)
    run_command(
        [
            str(python),
            "-c",
            (
                "from funasr import AutoModel; "
                "AutoModel(model='iic/SenseVoiceSmall', disable_update=True)"
            ),
        ]
    )
    _progress(on_progress, "models", "Downloading Moonshine Voice", 90)
    run_command(
        [
            str(python),
            "-c",
            (
                "from moonshine_voice import ModelArch, get_model_for_language; "
                "get_model_for_language("
                "wanted_language='en', "
                "wanted_model_arch=ModelArch.MEDIUM_STREAMING)"
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Install / uninstall (model-aware)
# ---------------------------------------------------------------------------


def install_model(
    slug: str,
    *,
    model_id: str,
    runtime: str,
    spec: str | None = None,
    device: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Ensure environment and download a single model by *slug*."""
    ensure_environment(device=device, on_progress=on_progress)
    python = python_bin()
    download_model(
        python,
        model_id=model_id,
        runtime=runtime,
        spec=spec,
        on_progress=on_progress,
    )
    _progress(on_progress, "done", f"Model {slug} installed", 100)


def uninstall_model(cache_path: str) -> None:
    """Remove a single model cache directory."""
    path = Path(cache_path)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def uninstall_all(model_cache_paths: list[str]) -> None:
    """Remove all model caches and the ASR venv."""
    for cache_path in model_cache_paths:
        path = Path(cache_path)
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
    if VENV_DIR.exists():
        shutil.rmtree(VENV_DIR, ignore_errors=True)


# ---------------------------------------------------------------------------
# Full deploy (backward-compat)
# ---------------------------------------------------------------------------


def deploy(
    *,
    device: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Full deploy: venv + deps + torch + ALL models."""
    ensure_environment(device=device, on_progress=on_progress)
    python = python_bin()
    _progress(on_progress, "models", "Downloading ASR models", 50)
    download_models(python, on_progress=on_progress)
    _progress(on_progress, "done", "ASR environment ready", 100)


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy Memento ASR service")
    parser.add_argument("--device", choices=["cpu", "cuda"], default=None)
    args = parser.parse_args()
    deploy(
        device=args.device,
        on_progress=lambda stage, detail, percent=None: print(f"{stage}: {detail}"),
    )


if __name__ == "__main__":
    main()
