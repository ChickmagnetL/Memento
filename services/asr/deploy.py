"""Deploy the standalone Memento ASR service environment."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

# Capture any pre-existing HF_ENDPOINT before setdefault so download fallback
# can tell "user/parent forced a value" from "we filled the China default".
_USER_HF_ENDPOINT = os.environ.get("HF_ENDPOINT")
_DEFAULT_HF_ENDPOINTS = ("https://huggingface.co", "https://hf-mirror.com")
# Default to the official HuggingFace hub (moonshine models ship via HF).
# Harmless elsewhere; set HF_ENDPOINT to override. Download path may fall back.
os.environ.setdefault("HF_ENDPOINT", _DEFAULT_HF_ENDPOINTS[0])


SERVICE_DIR = Path(__file__).resolve().parent
VENV_DIR = SERVICE_DIR / ".venv"
MODELS_DIR = SERVICE_DIR / "models"
SENSEVOICE_CACHE_DIR = MODELS_DIR / "sensevoice"
MOONSHINE_CACHE_DIR = MODELS_DIR / "moonshine"
CUDA_TORCH_INDEX_URL = os.environ.get(
    "CUDA_TORCH_INDEX_URL", "https://download.pytorch.org/whl/cu124"
)
# Tsinghua PyPI mirror by default; set PIP_INDEX_URL="" to use the default PyPI.
PIP_INDEX_URL = os.environ.get("PIP_INDEX_URL", "https://pypi.tuna.tsinghua.edu.cn/simple")

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

# CLI slug → (model_id, runtime, spec). Duplicated here on purpose — do not
# import from backend/node_app so this service remains standalone.
_MODEL_SLUGS: dict[str, dict[str, str | None]] = {
    "sensevoice-small": {
        "model_id": "iic/SenseVoiceSmall",
        "runtime": "sensevoice",
        "spec": None,
    },
    "moonshine-tiny-en": {
        "model_id": "moonshine_voice/tiny-en",
        "runtime": "moonshine",
        "spec": "tiny-en",
    },
    "moonshine-base-en": {
        "model_id": "moonshine_voice/base-en",
        "runtime": "moonshine",
        "spec": "base-en",
    },
    "moonshine-tiny-streaming-en": {
        "model_id": "moonshine_voice/tiny-streaming-en",
        "runtime": "moonshine",
        "spec": "tiny-streaming-en",
    },
    "moonshine-small-streaming-en": {
        "model_id": "moonshine_voice/small-streaming-en",
        "runtime": "moonshine",
        "spec": "small-streaming-en",
    },
    "moonshine-medium-streaming-en": {
        "model_id": "moonshine_voice/medium-streaming-en",
        "runtime": "moonshine",
        "spec": "medium-streaming-en",
    },
}


def python_bin() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run_command(
    args: list[str | Path],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    subprocess.run(
        [str(arg) for arg in args],
        cwd=str(cwd or SERVICE_DIR),
        check=True,
        env=env,
    )


def _ensure_managed_toolchain() -> None:
    node_service_dir = SERVICE_DIR.parent / "node"
    node_service_path = str(node_service_dir)
    if node_service_path not in sys.path:
        sys.path.insert(0, node_service_path)

    from node_app.toolchain import ensure_toolchain

    ensure_toolchain()


def _with_pip_index(command: list[str]) -> list[str]:
    """Append `-i PIP_INDEX_URL` to a pip command when a mirror is configured.

    No-op when PIP_INDEX_URL is empty (set PIP_INDEX_URL="" for the default PyPI).
    """
    if PIP_INDEX_URL:
        command.extend(["-i", PIP_INDEX_URL])
    return command


def _hf_endpoint_candidates() -> list[str]:
    """Return HuggingFace hub endpoints to try for model download.

    - Custom HF_ENDPOINT (not a known public hub): exclusive, no public fallback.
    - Unset, or a known public hub (incl. parent bootstrap setdefault): try the
      China mirror first, then the official hub, preferring any user-set known
      hub first.
    """
    defaults = list(_DEFAULT_HF_ENDPOINTS)
    user = (_USER_HF_ENDPOINT or "").strip().rstrip("/")
    if not user:
        return defaults
    known = {ep.rstrip("/") for ep in defaults}
    if user not in known:
        return [user]
    ordered = [user]
    for ep in defaults:
        if ep.rstrip("/") != user:
            ordered.append(ep)
    return ordered


def _run_with_hf_endpoint_fallback(
    args: list[str | Path],
    *,
    base_env: dict[str, str],
    what: str,
) -> None:
    """Run a command with HF_ENDPOINT fallback across candidate hubs."""
    candidates = _hf_endpoint_candidates()
    errors: list[str] = []
    for endpoint in candidates:
        env = dict(base_env)
        env["HF_ENDPOINT"] = endpoint
        # Force the HF HTTP bridge instead of the hf_xet native protocol, which
        # stalls large LFS downloads at 0 bytes/s on this network.
        env["HF_HUB_DISABLE_XET"] = "1"
        print(f"{what} via HF_ENDPOINT={endpoint}")
        try:
            run_command(args, env=env)
            print(f"{what} succeeded via {endpoint}")
            return
        except Exception as exc:
            print(f"{what} failed via {endpoint}: {exc}")
            errors.append(f"{endpoint}: {exc}")
    raise RuntimeError(
        f"Failed {what} from all HF endpoints. Tried: " + "; ".join(errors)
    )


def detect_best_device() -> str:
    """Detect the best available torch device: cuda > mps > cpu.

    Check host hardware first so a clean Settings deploy can select the right
    torch wheel before the service venv exists.  Fall back to probing the venv
    when the platform has no obvious accelerator.
    """
    if shutil.which("nvidia-smi") is not None:
        return "cuda"
    if sys.platform == "darwin":
        return "mps"

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


def _torch_cuda_available() -> bool:
    """Probe whether venv torch has CUDA support."""
    script = "import torch; print('1' if torch.cuda.is_available() else '0')"
    try:
        result = subprocess.run(
            [str(python_bin()), "-c", script],
            capture_output=True, text=True, timeout=60,
        )
        return result.stdout.strip() == "1"
    except Exception:
        return False


def _ensure_cuda_torch() -> None:
    """After install, if CUDA torch not actually usable, force reinstall from CUDA index."""
    if _torch_cuda_available():
        print("CUDA torch verified: torch.cuda.is_available() == True")
        return
    print("WARNING: torch installed but CUDA not available; force-reinstalling from CUDA index...")
    run_command([str(python_bin()), "-m", "pip", "uninstall", "-y", "torch", "torchaudio"])
    torch_cmd = [
        str(python_bin()), "-m", "pip", "install", "--force-reinstall",
        "torch", "torchaudio",
        "--index-url", CUDA_TORCH_INDEX_URL,
    ]
    # Do NOT append China pip mirror.
    run_command(torch_cmd)
    if _torch_cuda_available():
        print("CUDA torch force-reinstall succeeded: torch.cuda.is_available() == True")
    else:
        print(
            "WARNING: torch still has no CUDA after force-reinstall. "
            "Host may lack NVIDIA driver/CUDA, or wrong CUDA index. "
            "Service will fall back to CPU if started with ASR_DEVICE=cuda."
        )


def torch_install_command(use_cuda: bool = False) -> list[str]:
    """Return the pip install command for torch (+torchaudio), with CUDA index if needed."""
    command = [str(python_bin()), "-m", "pip", "install", "torch", "torchaudio"]
    if use_cuda:
        # CUDA torch wheels only ship on the pytorch index (no China mirror),
        # so use the official CDN index there; overridable via CUDA_TORCH_INDEX_URL.
        command.extend(["--index-url", CUDA_TORCH_INDEX_URL])
    else:
        _with_pip_index(command)
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
            if getattr(sys, "frozen", False):
                _ensure_managed_toolchain()
            else:
                run_command([sys.executable, "-m", "venv", str(VENV_DIR)])
            created_venv = True

        python = python_bin()
        _progress(on_progress, "dependencies", "Installing ASR dependencies", 30)
        run_command(
            _with_pip_index(
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
        )
        run_command(
            _with_pip_index(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    str(SERVICE_DIR / "requirements.txt"),
                ]
            )
        )

        _progress(on_progress, "torch", "Installing platform torch wheel", 45)
        use_cuda = bool(device == "cuda")
        run_command(torch_install_command(use_cuda=use_cuda))
        if use_cuda:
            _ensure_cuda_torch()

        _progress(on_progress, "environment", "ASR environment ready", 50)
    except Exception:
        if created_venv and VENV_DIR.exists():
            shutil.rmtree(VENV_DIR, ignore_errors=True)
        raise


# ---------------------------------------------------------------------------
# Model download
# ---------------------------------------------------------------------------


def _run_sensevoice_download(python: Path, model_id: str, cache_dir: Path) -> None:
    """Download a SenseVoice model via modelscope.

    model_id and cache_dir are passed through environment variables instead of
    being interpolated into the ``-c`` script string. Embedding a Windows path
    such as ``...\\services\\asr\\models\\sensevoice`` into the script would let
    Python's escape parsing mangle it (``\\a`` -> bell char 0x07, ``\\W`` ->
    invalid escape), corrupting the path at runtime.
    """
    env = dict(os.environ)
    env["MEM_DOWNLOAD_MODEL_ID"] = str(model_id)
    env["MEM_DOWNLOAD_CACHE_DIR"] = str(cache_dir)
    script = (
        "import os;"
        " from modelscope.hub.snapshot_download import snapshot_download;"
        " snapshot_download(os.environ['MEM_DOWNLOAD_MODEL_ID'],"
        " cache_dir=os.environ['MEM_DOWNLOAD_CACHE_DIR'])"
    )
    run_command([str(python), "-c", script], env=env)


def _run_moonshine_download(python: Path, arch: str, *, label: str) -> None:
    """Download a Moonshine model via HF, with endpoint fallback."""
    script = (
        "from moonshine_voice import ModelArch, get_model_for_language; "
        f"get_model_for_language(wanted_language='en', wanted_model_arch=ModelArch.{arch})"
    )
    _run_with_hf_endpoint_fallback(
        [str(python), "-c", script],
        base_env={**os.environ, "MOONSHINE_VOICE_CACHE": str(MOONSHINE_CACHE_DIR)},
        what=f"Downloading {label}",
    )


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
        _run_sensevoice_download(python, model_id, SENSEVOICE_CACHE_DIR)
    elif runtime == "moonshine":
        if spec is None or spec not in _SPEC_TO_ARCH:
            raise ValueError(f"Unknown moonshine spec: {spec}")
        arch = _SPEC_TO_ARCH[spec]
        _run_moonshine_download(python, arch, label=label)
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
    _run_sensevoice_download(python, "iic/SenseVoiceSmall", SENSEVOICE_CACHE_DIR)
    _progress(on_progress, "models", "Downloading Moonshine Voice", 90)
    _run_moonshine_download(python, "MEDIUM_STREAMING", label="Moonshine Voice")


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
    if device is None:
        device = detect_best_device()
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
# Model presence checks (skip re-download when already cached)
# ---------------------------------------------------------------------------


def _sensevoice_present() -> bool:
    """True if SenseVoiceSmall cache looks installed (same heuristic as bootstrap)."""
    root = MODELS_DIR / "sensevoice"
    if not root.is_dir():
        return False
    if (root / "iic" / "SenseVoiceSmall" / "model.pt").is_file():
        return True
    return any(root.rglob("model.pt"))


def _moonshine_present() -> bool:
    """True if medium-streaming-en quantized cache is present (same as bootstrap)."""
    return (
        MODELS_DIR
        / "moonshine"
        / "download.moonshine.ai"
        / "model"
        / "medium-streaming-en"
        / "quantized"
    ).is_dir()


# ---------------------------------------------------------------------------
# Full deploy (backward-compat)
# ---------------------------------------------------------------------------


def deploy(
    *,
    device: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Full deploy: always repair env (venv/deps/torch); download only missing models."""
    if device is None:
        device = detect_best_device()
    ensure_environment(device=device, on_progress=on_progress)
    python = python_bin()

    sense_ok = _sensevoice_present()
    moon_ok = _moonshine_present()
    if sense_ok and moon_ok:
        _progress(on_progress, "models", "ASR models already present, skipping download", 90)
        print("ASR models: all present, skipping download.")
    else:
        if not sense_ok:
            _progress(on_progress, "models", "Downloading SenseVoiceSmall", 50)
            print("ASR models: downloading SenseVoiceSmall...")
            _run_sensevoice_download(python, "iic/SenseVoiceSmall", SENSEVOICE_CACHE_DIR)
        else:
            _progress(on_progress, "models", "SenseVoiceSmall present, skipping", 50)
            print("ASR models: SenseVoiceSmall present, skipping download.")
        if not moon_ok:
            _progress(on_progress, "models", "Downloading Moonshine Voice", 90)
            print("ASR models: downloading Moonshine Voice...")
            _run_moonshine_download(python, "MEDIUM_STREAMING", label="Moonshine Voice")
        else:
            _progress(on_progress, "models", "Moonshine Voice present, skipping", 90)
            print("ASR models: Moonshine Voice present, skipping download.")

    _progress(on_progress, "done", "ASR environment ready", 100)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Deploy Memento ASR service. "
            "Override HF hub with HF_ENDPOINT; Moonshine download falls back "
            "across https://hf-mirror.com and https://huggingface.co when unset."
        ),
    )
    parser.add_argument("--device", choices=["cpu", "cuda", "mps", "auto"], default="auto")
    parser.add_argument(
        "--env-only",
        action="store_true",
        help="Only ensure the Python environment (venv/deps/torch); skip model downloads.",
    )
    parser.add_argument(
        "--models",
        default="",
        help=(
            "Comma-separated model slugs to install "
            f"(choices: {', '.join(_MODEL_SLUGS)})."
        ),
    )
    args = parser.parse_args()
    device = args.device if args.device != "auto" else detect_best_device()
    on_progress = lambda stage, detail, percent=None: print(f"{stage}: {detail}")

    if args.env_only:
        ensure_environment(device=device, on_progress=on_progress)
        return

    model_slugs = [s.strip() for s in args.models.split(",") if s.strip()]
    if model_slugs:
        for slug in model_slugs:
            if slug not in _MODEL_SLUGS:
                raise SystemExit(
                    f"Unknown ASR model slug: {slug!r}. "
                    f"Valid slugs: {', '.join(_MODEL_SLUGS)}"
                )
        for slug in model_slugs:
            info = _MODEL_SLUGS[slug]
            install_model(
                slug=slug,
                model_id=str(info["model_id"]),
                runtime=str(info["runtime"]),
                spec=info["spec"],
                device=device,
                on_progress=on_progress,
            )
        return

    deploy(device=device, on_progress=on_progress)


if __name__ == "__main__":
    main()
