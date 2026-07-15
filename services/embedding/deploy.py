#!/usr/bin/env python3
"""Deploy the Memento embedding service: venv, deps, torch, model download."""

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
# Default to the official HuggingFace hub for runtime / non-download paths.
# Harmless elsewhere; set HF_ENDPOINT to override. Download path may fall back.
os.environ.setdefault("HF_ENDPOINT", _DEFAULT_HF_ENDPOINTS[0])

SERVICE_DIR = Path(__file__).resolve().parent
VENV_DIR = SERVICE_DIR / ".venv"
MODELS_DIR = SERVICE_DIR / "models"
CUDA_TORCH_INDEX_URL = os.environ.get(
    "CUDA_TORCH_INDEX_URL", "https://download.pytorch.org/whl/cu124"
)
# Tsinghua PyPI mirror by default; set PIP_INDEX_URL="" to use the default PyPI.
PIP_INDEX_URL = os.environ.get("PIP_INDEX_URL", "https://pypi.tuna.tsinghua.edu.cn/simple")
DEFAULT_MODEL = "BAAI/bge-m3"
_CONFIG_NAMES = ("config.json", "modules.json", "config_sentence_transformers.json")

ProgressCallback = Callable[[str, str, int | None], None]


def python_bin() -> Path:
    """Return the venv python binary path."""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run_command(
    args: list[str | Path],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    """Run a command via subprocess, raising on non-zero exit."""
    subprocess.run([str(a) for a in args], cwd=cwd, check=True, env=env)


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


def detect_best_device() -> str:
    """Detect the best available torch device: cuda > mps > cpu.

    Check host hardware before the service venv so a clean Settings deploy
    installs the correct platform torch build.
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
    run_command([str(python_bin()), "-m", "pip", "uninstall", "-y", "torch"])
    torch_cmd = [
        str(python_bin()), "-m", "pip", "install", "--force-reinstall", "torch",
        "--index-url", CUDA_TORCH_INDEX_URL,
    ]
    # Do NOT append China pip mirror index — only pytorch CUDA index.
    run_command(torch_cmd)
    if _torch_cuda_available():
        print("CUDA torch force-reinstall succeeded: torch.cuda.is_available() == True")
    else:
        print(
            "WARNING: torch still has no CUDA after force-reinstall. "
            "Host may lack NVIDIA driver/CUDA, or wrong CUDA index. "
            "Service will fall back to CPU if started with EMBEDDING_DEVICE=cuda."
        )


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
            if getattr(sys, "frozen", False):
                _ensure_managed_toolchain()
            else:
                run_command([sys.executable, "-m", "venv", str(VENV_DIR)])
            created_venv = True

        _progress(on_progress, "venv", "Upgrading pip/setuptools/wheel", 10)
        run_command(_with_pip_index([
            str(python_bin()), "-m", "pip", "install",
            "--upgrade", "pip", "setuptools", "wheel",
        ]))

        _progress(on_progress, "deps", "Installing Python dependencies", 20)
        run_command(_with_pip_index([
            str(python_bin()), "-m", "pip", "install",
            "-r", str(SERVICE_DIR / "requirements.txt"),
        ]))

        _progress(on_progress, "torch", f"Installing torch (device={device})", 35)
        torch_cmd = [
            str(python_bin()), "-m", "pip", "install", "torch",
        ]
        if device == "cuda":
            torch_cmd.extend(["--index-url", CUDA_TORCH_INDEX_URL])
        else:
            _with_pip_index(torch_cmd)
        run_command(torch_cmd)
        if device == "cuda":
            _ensure_cuda_torch()
    except Exception:
        if created_venv and VENV_DIR.is_dir():
            shutil.rmtree(VENV_DIR)
        raise


def download_model(model_id: str = DEFAULT_MODEL) -> None:
    """Download the embedding model via huggingface_hub.snapshot_download.

    Tries HF endpoints in order (China mirror then official by default).
    Resume is supported by default (partial cache is kept).
    """
    script = """
import os, sys
from huggingface_hub import snapshot_download

model_id = os.environ['MEM_DOWNLOAD_MODEL_ID']
cache_dir = os.environ['MEM_DOWNLOAD_CACHE_DIR']
print(f"snapshot_download {model_id} -> {cache_dir}", flush=True)
print("Tip: set HF_TOKEN if you hit rate limits.", flush=True)
print("Ctrl+C keeps partial cache for resume; re-run deploy to continue.", flush=True)
try:
    path = snapshot_download(
        repo_id=model_id,
        cache_dir=cache_dir,
        max_workers=1,
    )
    print(f"snapshot_download finished: {path}", flush=True)
except KeyboardInterrupt:
    print(
        "Download interrupted / 下载已中断: partial cache kept for resume; "
        "re-run deploy to continue / 已保留断点缓存，重新运行 deploy 可续传",
        flush=True,
    )
    sys.exit(130)
"""
    candidates = _hf_endpoint_candidates()
    errors: list[str] = []
    models_dir = str(MODELS_DIR)
    for endpoint in candidates:
        env = dict(os.environ)
        env["HF_ENDPOINT"] = endpoint
        env["MEM_DOWNLOAD_MODEL_ID"] = str(model_id)
        env["MEM_DOWNLOAD_CACHE_DIR"] = models_dir
        # Force all hub/transformers caches under MODELS_DIR (not user home).
        env["HF_HOME"] = models_dir
        env["HUGGINGFACE_HUB_CACHE"] = models_dir
        env["TRANSFORMERS_CACHE"] = models_dir
        env["HF_HUB_CACHE"] = models_dir
        env["PYTHONUNBUFFERED"] = "1"
        env["HF_HUB_DISABLE_SYMLINKS"] = "1"
        env["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
        env["HF_HUB_DISABLE_XET"] = "1"
        print(f"Downloading embedding model via HF_ENDPOINT={endpoint}")
        try:
            run_command([str(python_bin()), "-c", script], env=env)
            present = _model_present(model_id)
            weights = _list_weight_files(model_id)
            print(f"post-download check: _model_present({model_id})={present}")
            if weights:
                for path, size_mb in weights:
                    print(f"  weight: {path} ({size_mb:.2f} MB)")
            else:
                print("  weight: (none found)")
            if present:
                print(f"Embedding model download succeeded via {endpoint}")
                return
            msg = f"{endpoint}: download finished but weights still missing"
            print(f"Embedding model download incomplete via {endpoint}: weights still missing")
            errors.append(msg)
        except subprocess.CalledProcessError as exc:
            if exc.returncode == 130:
                print(
                    "Download interrupted / 下载已中断: partial cache kept for resume; "
                    "re-run deploy to continue / 已保留断点缓存，重新运行 deploy 可续传",
                )
                raise SystemExit(130) from exc
            print(f"Embedding model download failed via {endpoint}: {exc}")
            errors.append(f"{endpoint}: {exc}")
        except KeyboardInterrupt:
            print(
                "Download interrupted / 下载已中断: partial cache kept for resume; "
                "re-run deploy to continue / 已保留断点缓存，重新运行 deploy 可续传",
            )
            raise SystemExit(130)
        except Exception as exc:
            print(f"Embedding model download failed via {endpoint}: {exc}")
            errors.append(f"{endpoint}: {exc}")
    raise RuntimeError(
        "Failed to download embedding model from all HF endpoints. Tried: "
        + "; ".join(errors)
    )


def _cache_has_model_weights(cache_dir: Path) -> bool:
    """True if cache_dir contains complete model weight files (not just config/tokenizer).

    Index alone is NOT enough — requires actual weight files >1MB.
    """
    if not cache_dir.is_dir():
        return False
    # Single-file weights must be large enough to be more than a stub/partial file.
    for name in ("model.safetensors", "pytorch_model.bin"):
        for p in cache_dir.rglob(name):
            try:
                if p.is_file() and p.stat().st_size > 1_000_000:
                    return True
            except OSError:
                continue
    # Sharded or alternate names: any large safetensors shard is enough.
    for p in cache_dir.rglob("*.safetensors"):
        try:
            if p.is_file() and p.stat().st_size > 1_000_000:
                return True
        except OSError:
            continue
    return False


def _dir_is_complete_model(path: Path) -> bool:
    return (
        any((path / name).is_file() for name in _CONFIG_NAMES)
        and _cache_has_model_weights(path)
    )


def _model_cache_dirs(model_id: str) -> list[Path]:
    """Return candidate HF cache dirs for *model_id* under MODELS_DIR."""
    slug = model_id.replace("/", "--")
    return [
        MODELS_DIR / f"models--{slug}",
        MODELS_DIR / f"models--sentence-transformers--{slug}",
    ]


def _list_weight_files(model_id: str) -> list[tuple[Path, float]]:
    """List weight files under model cache dirs as (path, size_mb)."""
    found: list[tuple[Path, float]] = []
    seen: set[Path] = set()
    names = ("pytorch_model.bin", "model.safetensors")
    for cache_dir in _model_cache_dirs(model_id):
        if not cache_dir.is_dir():
            continue
        candidates: list[Path] = []
        for name in names:
            candidates.extend(cache_dir.rglob(name))
        candidates.extend(cache_dir.rglob("*.safetensors"))
        for p in candidates:
            try:
                resolved = p.resolve()
                if resolved in seen or not p.is_file():
                    continue
                seen.add(resolved)
                size_mb = p.stat().st_size / (1024 * 1024)
                found.append((p, size_mb))
            except OSError:
                continue
    found.sort(key=lambda item: str(item[0]))
    return found


def _model_present(model_id: str = DEFAULT_MODEL) -> bool:
    """True if the model cache has complete weight files for *model_id*.

    Checks both direct HF hub layout (models--org--name) and the legacy
    sentence-transformers prefix (models--sentence-transformers--...).
    """
    return _find_local_model_path(model_id) is not None


def _find_local_model_path(model_id: str) -> Path | None:
    """Resolve a filesystem path to local model weights, or None if incomplete/missing."""
    for root in _model_cache_dirs(model_id):
        if not root.is_dir():
            continue
        snapshots = root / "snapshots"
        if snapshots.is_dir():
            try:
                snap_dirs = [p for p in snapshots.iterdir() if p.is_dir()]
            except OSError:
                snap_dirs = []
            snap_dirs.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
            for snap in snap_dirs:
                if _dir_is_complete_model(snap):
                    return snap
        if _dir_is_complete_model(root):
            return root
    return None


def uninstall_model(model_id: str) -> None:
    """Remove only the managed cache roots for one model."""
    for path in _model_cache_dirs(model_id):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


def uninstall_all() -> None:
    """Remove the local Embedding environment and managed model cache."""
    if MODELS_DIR.exists():
        shutil.rmtree(MODELS_DIR, ignore_errors=True)
    if VENV_DIR.exists():
        shutil.rmtree(VENV_DIR, ignore_errors=True)


def deploy(
    *,
    device: str | None = None,
    model_id: str = DEFAULT_MODEL,
    env_only: bool = False,
    force_model: bool = False,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Full deploy: always repair env (venv/deps/torch); download model only if missing.

    When *env_only* is True, skip model download entirely (even if missing).
    When *force_model* is True, wipe model cache and re-download.
    Incomplete cache is kept so snapshot_download can resume.
    """
    if device is None:
        device = detect_best_device()
    _progress(on_progress, "env", f"Deploying embedding environment (device={device})", 0)
    ensure_environment(device=device, on_progress=on_progress)
    if env_only:
        _progress(on_progress, "done", f"Embedding environment ready (device={device})", 100)
        return
    if force_model:
        print(f"Force re-download for {model_id}...")
        for p in _model_cache_dirs(model_id):
            if p.is_dir():
                shutil.rmtree(p)
    if _model_present(model_id):
        _progress(on_progress, "model", f"Model {model_id} present, skipping download", 90)
        print(f"Embedding model {model_id}: present, skipping download.")
    else:
        if any(p.is_dir() for p in _model_cache_dirs(model_id)):
            print(f"incomplete cache for {model_id}, resuming download...")
        else:
            print(f"Embedding model {model_id}: missing; downloading...")
        _progress(on_progress, "model", f"Downloading model {model_id}", 50)
        download_model(model_id)
        if not _model_present(model_id):
            raise RuntimeError(
                f"Embedding model {model_id} weights still missing after download"
            )
    local = _find_local_model_path(model_id)
    if local:
        print(f"Resolved local model path: {local}")
    _progress(on_progress, "done", f"Embedding environment ready (device={device})", 100)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Deploy Memento Embedding service. "
            "Override HF hub with HF_ENDPOINT; download falls back across "
            "https://hf-mirror.com and https://huggingface.co when unset."
        ),
    )
    parser.add_argument(
        "--device", choices=["cpu", "cuda", "mps", "auto"], default="auto",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--env-only",
        action="store_true",
        help="Only ensure the Python environment (venv/deps/torch); skip model download.",
    )
    parser.add_argument(
        "--force-model",
        action="store_true",
        help="Force re-download of the embedding model (wipes existing cache).",
    )
    args = parser.parse_args()
    device = detect_best_device() if args.device == "auto" else args.device
    deploy(
        device=device,
        model_id=args.model,
        env_only=args.env_only,
        force_model=args.force_model,
        on_progress=lambda stage, detail, percent=None: print(f"{stage}: {detail}"),
    )


if __name__ == "__main__":
    main()
