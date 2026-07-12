from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

try:
    from .paths import ASR_DIR, BIN_DIR, EMBEDDING_DIR, PYTHON_DIR
    from .device import _venv_python
except ImportError:
    from node_app_paths import ASR_DIR, BIN_DIR, EMBEDDING_DIR, PYTHON_DIR  # type: ignore
    from node_app_device import _venv_python  # type: ignore


UV_RELEASE_BASE = "https://github.com/astral-sh/uv/releases/latest/download"
# Fallback PyPI index for unstable networks: GitHub release redirects
# (objects.githubusercontent.com) are often disrupted in China, while the PyPI
# `uv` wheel carries the same standalone binary and is mirrored domestically.
UV_PIP_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"
_UV_DOWNLOAD_ATTEMPTS = 3


def _uv_path() -> Path:
    name = "uv.exe" if sys.platform == "win32" else "uv"
    return BIN_DIR / name


def _detect_uv_asset() -> dict:
    """Pick the uv standalone release asset for the current platform/arch."""
    machine = platform.machine().lower()
    is_x64 = machine in ("x86_64", "amd64")
    is_arm = machine in ("arm64", "aarch64")
    if sys.platform == "darwin":
        if is_arm:
            return {"name": "uv-aarch64-apple-darwin.tar.gz", "kind": "tar"}
        if is_x64:
            return {"name": "uv-x86_64-apple-darwin.tar.gz", "kind": "tar"}
    elif sys.platform.startswith("linux"):
        if is_arm:
            return {"name": "uv-aarch64-unknown-linux-gnu.tar.gz", "kind": "tar"}
        if is_x64:
            return {"name": "uv-x86_64-unknown-linux-gnu.tar.gz", "kind": "tar"}
    elif sys.platform == "win32":
        if is_arm:
            return {"name": "uv-aarch64-pc-windows-msvc.zip", "kind": "zip"}
        if is_x64:
            return {"name": "uv-x86_64-pc-windows-msvc.zip", "kind": "zip"}
    raise RuntimeError(f"Unsupported platform/arch: {sys.platform}/{machine}")


def _place_uv_from_archive(td: Path, asset: dict, uv: Path) -> None:
    """Extract the standalone uv binary from a downloaded GitHub archive into BIN_DIR."""
    archive = td / asset["name"]
    exe_name = "uv.exe" if sys.platform == "win32" else "uv"
    if asset["kind"] == "tar":
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(td)
    else:
        with zipfile.ZipFile(archive) as z:
            z.extractall(td)
    candidates = [p for p in td.rglob(exe_name) if p.is_file()]
    if not candidates:
        raise RuntimeError(f"{exe_name} not found in {asset['name']}")
    shutil.move(str(candidates[0]), str(uv))


def _place_uv_from_pip(td: Path, uv: Path) -> None:
    """Install the standalone uv binary via a China-friendly PyPI mirror.

    The PyPI `uv` wheel ships the same binary; `pip install --target` places it at
    <td>/bin/uv (Unix) or <td>/Scripts/uv.exe (Windows). Used when the direct
    GitHub download fails on an unstable connection (e.g. GFW interference).
    """
    exe_name = "uv.exe" if sys.platform == "win32" else "uv"
    cmd = [sys.executable, "-m", "pip", "install", "--target", str(td),
           "uv", "--no-deps", "-i", UV_PIP_INDEX]
    subprocess.run(cmd, check=True)
    candidates = [p for p in td.rglob(exe_name) if p.is_file()]
    if not candidates:
        raise RuntimeError(f"{exe_name} not found in pip-installed uv package")
    shutil.move(str(candidates[0]), str(uv))


def _ensure_uv() -> Path:
    """Download the standalone uv binary into services/.bin/ if missing. Returns its path.

    Tries the direct GitHub release first with retry + backoff; on persistent
    failure falls back to the PyPI `uv` package via a China-friendly mirror, which
    stays reachable when GitHub release redirects are disrupted.
    """
    uv = _uv_path()
    if uv.exists():
        return uv
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    asset = _detect_uv_asset()
    url = f"{UV_RELEASE_BASE}/{asset['name']}"

    primary_err = None
    with tempfile.TemporaryDirectory(dir=str(BIN_DIR)) as td:
        td_path = Path(td)
        # 1) Direct download from GitHub, with retry + backoff.
        for attempt in range(1, _UV_DOWNLOAD_ATTEMPTS + 1):
            try:
                print(f"  Downloading uv (attempt {attempt}/{_UV_DOWNLOAD_ATTEMPTS}): {url}")
                urlretrieve(url, td_path / asset["name"])
                _place_uv_from_archive(td_path, asset, uv)
                break
            except Exception as exc:  # SSLEOFError, URLError, corrupt archive, ...
                primary_err = exc
                if attempt < _UV_DOWNLOAD_ATTEMPTS:
                    print(f"    failed ({exc}); retrying in {2 * attempt}s ...")
                    time.sleep(2 * attempt)
        else:
            # 2) All direct attempts failed — fall back to the PyPI mirror.
            print(f"  Direct download failed ({primary_err}).")
            print(f"  Falling back to PyPI mirror: {UV_PIP_INDEX}")
            try:
                with tempfile.TemporaryDirectory(dir=str(BIN_DIR)) as ptd:
                    _place_uv_from_pip(Path(ptd), uv)
            except Exception as fallback_err:
                raise RuntimeError(
                    "uv download failed via both GitHub and the PyPI mirror.\n"
                    f"  GitHub error:    {primary_err}\n"
                    f"  PyPI mirror error: {fallback_err}\n"
                    "Please configure a proxy or VPN and retry, or manually place\n"
                    f"the uv binary for your platform at {uv}."
                ) from fallback_err

    if sys.platform != "win32":
        uv.chmod(0o755)
    print(f"  uv ready: {uv}")
    return uv


def _uv_env() -> dict:
    """Environment for uv: managed Pythons install under services/.python."""
    env = dict(os.environ)
    env["UV_PYTHON_INSTALL_DIR"] = str(PYTHON_DIR)
    return env


def _ensure_python_312() -> None:
    """Install Python 3.12 into services/.python/ via uv (idempotent)."""
    uv = _ensure_uv()
    PYTHON_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  Ensuring Python 3.12 in {PYTHON_DIR} ...")
    subprocess.run(
        [str(uv), "python", "install", "3.12"],
        env=_uv_env(), check=True,
    )


def _create_venvs() -> None:
    """Create per-service venvs (Python 3.12, seeded with pip) if missing.

    --seed installs pip/setuptools/wheel so the existing deploy.py scripts can
    use `python -m pip install` inside the venv.
    """
    uv = _ensure_uv()
    env = _uv_env()
    for service_dir, name in ((ASR_DIR, "asr"), (EMBEDDING_DIR, "embedding")):
        venv_dir = service_dir / ".venv"
        if venv_dir.exists():
            print(f"  {name} venv already exists, skipping.")
            continue
        print(f"  Creating {name} venv (Python 3.12) at {venv_dir} ...")
        subprocess.run(
            [str(uv), "venv", "--python", "3.12", "--seed", str(venv_dir)],
            env=env, check=True,
        )
        result = subprocess.run(
            [str(_venv_python(service_dir)), "--version"],
            capture_output=True, text=True, check=True,
        )
        version = result.stdout.strip()
        assert version.startswith("Python 3.12"), (
            f"{name} venv python is {version!r}, expected 3.12"
        )
        print(f"    {name} venv: {version}")


def ensure_toolchain() -> None:
    """uv + py3.12 + asr/embedding venvs."""
    _ensure_uv()
    _ensure_python_312()
    _create_venvs()
