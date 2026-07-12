"""Start and supervise ASR + Embedding HTTP services."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

try:
    from .paths import ASR_DIR, EMBEDDING_DIR
    from .ports import ASR_PORT, EMBEDDING_PORT
    from .device import _detect_device_in_venv, _venv_uvicorn
except ImportError:
    from node_app_paths import ASR_DIR, EMBEDDING_DIR  # type: ignore
    from node_app_ports import ASR_PORT, EMBEDDING_PORT  # type: ignore
    from node_app_device import _detect_device_in_venv, _venv_uvicorn  # type: ignore


def get_lan_ip() -> str:
    """Best-effort LAN IP via UDP connect trick; fall back to loopback."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def check_health(port: int, timeout: float = 2.0) -> bool:
    """Return True if localhost:{port}/health responds HTTP 200."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def wait_for_health(port: int, timeout: float = 60.0) -> bool:
    """Poll /health every 1s until ready or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check_health(port, timeout=1.0):
            return True
        time.sleep(1)
    return False


def start_asr(device: str) -> subprocess.Popen:
    """Start the ASR uvicorn process; logs append to ASR_DIR/logs/server.log."""
    uvicorn = _venv_uvicorn(ASR_DIR)
    if not uvicorn.exists():
        raise FileNotFoundError(
            f"ASR venv not found at {ASR_DIR / '.venv'}. Run 'deploy' first."
        )

    log_dir = ASR_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_fh = open(log_dir / "server.log", "a")  # noqa: SIM115 — kept open for child lifetime

    return subprocess.Popen(
        [str(uvicorn), "server:app", "--host", "0.0.0.0", "--port", str(ASR_PORT)],
        cwd=str(ASR_DIR),
        env={
            **os.environ,
            "ASR_HOST": "0.0.0.0",
            "ASR_PORT": str(ASR_PORT),
            "ASR_DEVICE": device,
            "MOONSHINE_VOICE_CACHE": str(ASR_DIR / "models" / "moonshine"),
        },
        stdout=log_fh,
        stderr=log_fh,
        start_new_session=True,
    )


def start_embedding(device: str) -> subprocess.Popen:
    """Start the Embedding uvicorn process; logs append to EMBEDDING_DIR/logs/server.log."""
    uvicorn = _venv_uvicorn(EMBEDDING_DIR)
    if not uvicorn.exists():
        raise FileNotFoundError(
            f"Embedding venv not found at {EMBEDDING_DIR / '.venv'}. Run 'deploy' first."
        )

    log_dir = EMBEDDING_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_fh = open(log_dir / "server.log", "a")  # noqa: SIM115 — kept open for child lifetime

    return subprocess.Popen(
        [str(uvicorn), "server:app", "--host", "0.0.0.0", "--port", str(EMBEDDING_PORT)],
        cwd=str(EMBEDDING_DIR),
        env={
            **os.environ,
            "EMBEDDING_HOST": "0.0.0.0",
            "EMBEDDING_PORT": str(EMBEDDING_PORT),
            "EMBEDDING_DEVICE": device,
        },
        stdout=log_fh,
        stderr=log_fh,
        start_new_session=True,
    )


def warmup_service(port: int, name: str, timeout: float = 600.0) -> None:
    """POST /v1/warmup; raise RuntimeError on non-200 or network failure."""
    url = f"http://127.0.0.1:{port}/v1/warmup"
    print(f"  Warming up {name} (POST {url})...")
    req = urllib.request.Request(url, method="POST", data=b"")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise RuntimeError(f"{name} warmup returned HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        detail = f"{e}"
        if body:
            detail = f"{e}: {body}"
        raise RuntimeError(f"{name} warmup failed: {detail}") from e
    except Exception as e:
        raise RuntimeError(f"{name} warmup failed: {e}") from e
    print(f"  {name} warmup complete.")



def cleanup(procs: list) -> None:
    """Terminate child processes, wait briefly, then kill stragglers."""
    for proc in procs:
        try:
            proc.terminate()
        except Exception:
            pass
    for proc in procs:
        try:
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def cmd_serve(*, warm: bool = False) -> None:
    """Start ASR + Embedding (skip already-healthy ports), optional warmup, then block."""
    asr_device = _detect_device_in_venv(ASR_DIR)
    emb_device = _detect_device_in_venv(EMBEDDING_DIR)
    print(f"Starting services (asr_device={asr_device}, embedding_device={emb_device})...")

    procs: list = []

    if check_health(ASR_PORT):
        print(f"  ASR service already running on port {ASR_PORT}")
    else:
        print(f"  Starting ASR service on port {ASR_PORT} (device={asr_device})...")
        asr_proc = start_asr(asr_device)
        procs.append(asr_proc)
        if not wait_for_health(ASR_PORT):
            print(f"  ERROR: ASR service failed to start on port {ASR_PORT}")
            cleanup(procs)
            sys.exit(1)
        print(f"  ASR service ready on port {ASR_PORT}")

    if check_health(EMBEDDING_PORT):
        print(f"  Embedding service already running on port {EMBEDDING_PORT}")
    else:
        print(f"  Starting embedding service on port {EMBEDDING_PORT} (device={emb_device})...")
        emb_proc = start_embedding(emb_device)
        procs.append(emb_proc)
        if not wait_for_health(EMBEDDING_PORT):
            print(f"  ERROR: Embedding service failed to start on port {EMBEDDING_PORT}")
            cleanup(procs)
            sys.exit(1)
        print(f"  Embedding service ready on port {EMBEDDING_PORT}")

    if warm:
        try:
            warmup_service(ASR_PORT, "ASR")
            warmup_service(EMBEDDING_PORT, "Embedding")
        except Exception as e:
            print(f"  ERROR: {e}")
            cleanup(procs)
            sys.exit(1)

    lan_ip = get_lan_ip()
    print()
    print("=" * 60)
    print("  Services running. Configure Memento Settings:")
    print()
    print(f"  ASR endpoint:       http://{lan_ip}:{ASR_PORT}/v1")
    print(f"  Embedding endpoint: http://{lan_ip}:{EMBEDDING_PORT}/v1")
    print()
    print(f"  ASR log:            {ASR_DIR / 'logs' / 'server.log'}")
    print(f"  Embedding log:      {EMBEDDING_DIR / 'logs' / 'server.log'}")
    print()
    print("  In Memento Settings, create presets with these endpoints.")
    print("  Provider: cloud (for embedding) or local (for ASR)")
    print("=" * 60)
    print()
    print("Press Ctrl+C to stop services started by this process.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        cleanup(procs)
