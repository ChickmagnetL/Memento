"""Lazy lifecycle management for the local Memento Embedding service."""

from __future__ import annotations

import atexit
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from urllib.request import urlopen

from config.settings import resolve_project_root


class EmbeddingServiceError(Exception):
    pass


_SPAWN_LOCK = threading.Lock()
_spawned_proc: subprocess.Popen | None = None
_cleanup_registered = False


def _default_venv_path() -> Path:
    venv = resolve_project_root() / "services" / "embedding" / ".venv"
    if sys.platform == "win32":
        return venv / "Scripts" / "uvicorn.exe"
    return venv / "bin" / "uvicorn"


def _managed_endpoint(endpoint: str) -> bool:
    parsed = urlparse(endpoint)
    return parsed.hostname in {"localhost", "127.0.0.1", "::1"} and parsed.port == 8003


def _health_base(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    return f"{parsed.scheme}://{parsed.netloc}"


def _is_healthy(endpoint: str, timeout: float = 1.0) -> bool:
    try:
        with urlopen(f"{_health_base(endpoint)}/health", timeout=timeout) as response:
            return response.status == 200
    except OSError:
        return False


def _spawn(venv: Path, port: int) -> subprocess.Popen:
    service_dir = resolve_project_root() / "services" / "embedding"
    options = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if sys.platform == "win32"
        else {"start_new_session": True}
    )
    return subprocess.Popen(
        [str(venv), "server:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(service_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        **options,
    )


def _terminate(proc: subprocess.Popen) -> None:
    if sys.platform == "win32":
        proc.terminate()
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except OSError:
        pass


def shutdown() -> None:
    global _spawned_proc
    if _spawned_proc is not None:
        _terminate(_spawned_proc)
        _spawned_proc = None


def ensure_embedding_running(
    endpoint: str,
    *,
    timeout: float = 120.0,
    poll_interval: float = 1.0,
    is_healthy: Callable[[str], bool] = _is_healthy,
    venv_path: Callable[[], Path] = _default_venv_path,
    spawn: Callable[[Path, int], subprocess.Popen] = _spawn,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    global _cleanup_registered, _spawned_proc
    if not _managed_endpoint(endpoint):
        return
    if is_healthy(endpoint):
        return
    venv = venv_path()
    if not venv.exists():
        return
    with _SPAWN_LOCK:
        if is_healthy(endpoint):
            return
        if _spawned_proc is not None and _spawned_proc.poll() is not None:
            _spawned_proc = None
        if _spawned_proc is None:
            _spawned_proc = spawn(venv, 8003)
            if not _cleanup_registered:
                atexit.register(shutdown)
                _cleanup_registered = True
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_healthy(endpoint):
            return
        if _spawned_proc is not None and _spawned_proc.poll() is not None:
            _spawned_proc = None
            raise EmbeddingServiceError(
                f"Embedding service failed to start at {_health_base(endpoint)}"
            )
        sleep(poll_interval)
    raise EmbeddingServiceError(
        f"Embedding service did not become healthy at {_health_base(endpoint)} within {timeout}s"
    )
