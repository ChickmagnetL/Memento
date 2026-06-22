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


def download_models(
    python: Path,
    *,
    on_progress: ProgressCallback | None = None,
) -> None:
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


def deploy(
    *,
    device: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> None:
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

        _progress(on_progress, "models", "Downloading ASR models", 50)
        download_models(python, on_progress=on_progress)

        _progress(on_progress, "done", "ASR environment ready", 100)
    except Exception:
        if created_venv and VENV_DIR.exists():
            shutil.rmtree(VENV_DIR, ignore_errors=True)
        raise


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
