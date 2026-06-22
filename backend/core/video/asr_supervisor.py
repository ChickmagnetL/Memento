"""Lazy supervisor for the standalone ASR service.

The ASR service runs in its own venv (services/asr) because funasr/torch are
heavy, so it is not started with the rest of the app. When the backend needs
to transcribe a video without subtitles, this supervisor transparently spawns
the ASR service from its venv if it is not already running, then waits for it
to become healthy. The user never has to start the service manually.

The spawned process is terminated on backend exit (atexit) so it does not
linger between sessions.
"""

import atexit
import logging
import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from urllib.request import urlopen

from config.settings import resolve_project_root

logger = logging.getLogger("memento.asr_supervisor")


class AsrError(Exception):
    """Raised when the ASR service cannot be reached or started."""


_SPAWN_LOCK = threading.Lock()
_spawned_proc: subprocess.Popen | None = None
_cleanup_registered = False


def _default_venv_path() -> Path:
    return resolve_project_root() / "services" / "asr" / ".venv" / "bin" / "uvicorn"


def _is_healthy(endpoint: str, timeout: float = 1.0) -> bool:
    try:
        with urlopen(f"{endpoint}/health", timeout=timeout) as response:
            return response.status == 200
    except OSError:
        return False


def _port_from_endpoint(endpoint: str) -> int:
    parsed = urlparse(endpoint)
    if parsed.port:
        return parsed.port
    return 443 if parsed.scheme == "https" else 80


def _is_local_endpoint(endpoint: str) -> bool:
    return urlparse(endpoint).hostname in {"localhost", "127.0.0.1", "::1"}


def _spawn(venv: Path, port: int) -> subprocess.Popen:
    project_root = resolve_project_root()
    return subprocess.Popen(
        [str(venv), "server:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(project_root / "services" / "asr"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )


def _terminate(proc: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except OSError:
        # Process already gone or not ours; nothing to do.
        pass


def _cleanup() -> None:
    shutdown()


def _startup_error(proc: subprocess.Popen) -> str:
    try:
        _, stderr = proc.communicate(timeout=0.1)
    except Exception:
        return "process exited before becoming healthy"
    if isinstance(stderr, bytes):
        detail = stderr.decode("utf-8", errors="replace").strip()
    else:
        detail = str(stderr or "").strip()
    return detail[-1000:] or "process exited before becoming healthy"


def shutdown() -> None:
    """Terminate a previously spawned ASR service process, if any.

    Called from the backend's lifespan teardown (reliable on graceful exit)
    and registered via atexit as a fallback.
    """
    global _spawned_proc
    if _spawned_proc is not None:
        _terminate(_spawned_proc)
        _spawned_proc = None


def ensure_asr_running(
    endpoint: str,
    *,
    timeout: float = 120.0,
    poll_interval: float = 1.0,
    is_healthy: Callable[[str], bool] = _is_healthy,
    venv_path: Callable[[], Path] = _default_venv_path,
    spawn: Callable[[Path, int], subprocess.Popen] = _spawn,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Ensure the ASR service at ``endpoint`` is reachable.

    If it is already healthy, returns immediately. Otherwise, if the ASR venv
    is installed, spawns the service and waits for it to become healthy. If the
    venv is not installed, returns without raising so the caller surfaces its
    usual "service unreachable" error.
    """
    global _spawned_proc

    if not _is_local_endpoint(endpoint):
        return

    if is_healthy(endpoint):
        return

    venv = venv_path()
    if not venv.exists():
        return

    with _SPAWN_LOCK:
        if is_healthy(endpoint):
            return
        # If a previously spawned process has since exited, clear it so we
        # respawn instead of waiting on a dead service.
        if _spawned_proc is not None and _spawned_proc.poll() is not None:
            _spawned_proc = None
        if _spawned_proc is None:
            port = _port_from_endpoint(endpoint)
            logger.info("ASR service not running; spawning from %s", venv)
            _spawned_proc = spawn(venv, port)
            global _cleanup_registered
            if not _cleanup_registered:
                atexit.register(_cleanup)
                _cleanup_registered = True

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_healthy(endpoint):
            logger.info("ASR service ready at %s", endpoint)
            return
        if _spawned_proc is not None and _spawned_proc.poll() is not None:
            detail = _startup_error(_spawned_proc)
            _spawned_proc = None
            raise AsrError(f"ASR service failed to start at {endpoint}: {detail}")
        sleep(poll_interval)
    raise AsrError(
        f"ASR service did not become healthy at {endpoint} within {timeout}s"
    )
