#!/usr/bin/env python3
"""Memento Remote Node Bootstrap — isolated toolchain + launcher.

Usage:
  python bootstrap.py                # interactive arrow-key menu
  python bootstrap.py probe          # detect hardware + check models
  python bootstrap.py deploy         # probe + build isolated venvs + install models
  python bootstrap.py serve          # start ASR + embedding services
  python bootstrap.py run            # deploy + serve (one-shot)

Self-contained: builds an isolated toolchain under services/ (uv + Python 3.12 +
per-service venvs) without touching the user's system Python. The system python
only LAUNCHES this script; all real work happens in services/.bin/uv and the
services-local Python 3.12. The interactive menu uses only the standard library.
"""

import os
import platform
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlretrieve, urlopen

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "services"
ASR_DIR = SERVICES_DIR / "asr"
EMBEDDING_DIR = SERVICES_DIR / "embedding"
BIN_DIR = SERVICES_DIR / ".bin"          # uv binary lives here
PYTHON_DIR = SERVICES_DIR / ".python"    # isolated managed Python 3.12

ASR_PORT = 8001
EMBEDDING_PORT = 8003

UV_RELEASE_BASE = "https://github.com/astral-sh/uv/releases/latest/download"


# ---------------------------------------------------------------------------
# venv path helpers (OS-correct)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Isolated toolchain: uv + Python 3.12 + per-service venvs
# ---------------------------------------------------------------------------

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


def _ensure_uv() -> Path:
    """Download the standalone uv binary into services/.bin/ if missing. Returns its path."""
    uv = _uv_path()
    if uv.exists():
        return uv
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    asset = _detect_uv_asset()
    url = f"{UV_RELEASE_BASE}/{asset['name']}"
    print(f"  Downloading uv: {url}")
    with tempfile.TemporaryDirectory(dir=str(BIN_DIR)) as td:
        archive = Path(td) / asset["name"]
        urlretrieve(url, archive)
        exe_name = "uv.exe" if sys.platform == "win32" else "uv"
        if asset["kind"] == "tar":
            with tarfile.open(archive, "r:gz") as tar:
                tar.extractall(td)
        else:
            with zipfile.ZipFile(archive) as z:
                z.extractall(td)
        candidates = [p for p in Path(td).rglob(exe_name) if p.is_file()]
        if not candidates:
            raise RuntimeError(f"{exe_name} not found in {asset['name']}")
        shutil.move(str(candidates[0]), str(uv))
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


# ---------------------------------------------------------------------------
# Hardware detection
# ---------------------------------------------------------------------------

def detect_best_device() -> str:
    """Detect the best available torch device.

    Strategy (in priority order):
    1. If ASR venv exists with torch, probe it (most accurate — confirms the
       installed torch actually sees CUDA/MPS).
    2. Else fall back to nvidia-smi (CUDA) / platform check (MPS on macOS).
       This works BEFORE the venv is built, so 'deploy' installs the right
       torch wheel (CUDA vs CPU) on the first run.
    """
    venv_python = _venv_python(ASR_DIR)
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

    # Venv not built yet — fall back to nvidia-smi / platform detection so
    # the first 'deploy' picks the right torch wheel (CUDA vs CPU).
    if shutil.which("nvidia-smi") is not None:
        return "cuda"
    if sys.platform == "darwin":
        return "mps"
    return "cpu"


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

def get_lan_ip() -> str:
    """Get the LAN IP address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

def check_health(port: int, timeout: float = 2.0) -> bool:
    """Check if a service is healthy on localhost:port."""
    try:
        resp = urlopen(f"http://127.0.0.1:{port}/health", timeout=timeout)
        return resp.status == 200
    except (URLError, OSError):
        return False


# ---------------------------------------------------------------------------
# Service launchers
# ---------------------------------------------------------------------------

def start_asr(device: str) -> subprocess.Popen:
    """Start the ASR service in the background. Returns the Popen handle."""
    venv_uvicorn = _venv_uvicorn(ASR_DIR)
    if not venv_uvicorn.exists():
        raise FileNotFoundError(f"ASR venv not found at {ASR_DIR / '.venv'}. Run 'deploy' first.")

    proc = subprocess.Popen(
        [str(venv_uvicorn), "server:app", "--host", "0.0.0.0", "--port", str(ASR_PORT)],
        cwd=str(ASR_DIR),
        env={
            **os.environ,
            "ASR_HOST": "0.0.0.0",
            "ASR_PORT": str(ASR_PORT),
            "ASR_DEVICE": device,
            "MOONSHINE_VOICE_CACHE": str(ASR_DIR / "models" / "moonshine"),
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return proc


def start_embedding(device: str) -> subprocess.Popen:
    """Start the embedding service in the background. Returns the Popen handle."""
    venv_uvicorn = _venv_uvicorn(EMBEDDING_DIR)
    if not venv_uvicorn.exists():
        raise FileNotFoundError(f"Embedding venv not found at {EMBEDDING_DIR / '.venv'}. Run 'deploy' first.")

    proc = subprocess.Popen(
        [str(venv_uvicorn), "server:app", "--host", "0.0.0.0", "--port", str(EMBEDDING_PORT)],
        cwd=str(EMBEDDING_DIR),
        env={**os.environ, "EMBEDDING_HOST": "0.0.0.0", "EMBEDDING_PORT": str(EMBEDDING_PORT), "EMBEDDING_DEVICE": device},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return proc


def wait_for_health(port: int, timeout: float = 60.0) -> bool:
    """Poll /health until the service is up or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check_health(port, timeout=1.0):
            return True
        time.sleep(1)
    return False


# ---------------------------------------------------------------------------
# Model existence checks
# ---------------------------------------------------------------------------

def check_asr_models() -> dict[str, bool]:
    """Check if ASR models are cached in services/asr/models/."""
    return {
        "iic/SenseVoiceSmall": (ASR_DIR / "models" / "sensevoice" / "iic" / "SenseVoiceSmall" / "model.pt").is_file(),
        "moonshine_voice/medium-streaming-en": (ASR_DIR / "models" / "moonshine" / "download.moonshine.ai" / "model" / "medium-streaming-en" / "quantized").is_dir(),
    }


def check_embedding_models() -> dict[str, bool]:
    """Check if embedding models are cached in services/embedding/models/."""
    model_dir = EMBEDDING_DIR / "models" / "models--sentence-transformers--all-MiniLM-L6-v2"
    return {"all-MiniLM-L6-v2": model_dir.is_dir()}


# ---------------------------------------------------------------------------
# Deployers
# ---------------------------------------------------------------------------

def deploy_asr(device: str) -> None:
    """Run the ASR service deploy.py (uses the pre-built 3.12 venv)."""
    deploy_script = ASR_DIR / "deploy.py"
    if not deploy_script.exists():
        print(f"ERROR: ASR deploy script not found at {deploy_script}")
        sys.exit(1)
    cmd = [sys.executable, str(deploy_script), "--device", device]
    print(f"  Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def deploy_embedding(device: str) -> None:
    """Run the embedding service deploy.py (uses the pre-built 3.12 venv)."""
    deploy_script = EMBEDDING_DIR / "deploy.py"
    if not deploy_script.exists():
        print(f"ERROR: Embedding deploy script not found at {deploy_script}")
        sys.exit(1)
    cmd = [sys.executable, str(deploy_script), "--device", device]
    print(f"  Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_probe() -> None:
    """Print hardware and model status."""
    device = detect_best_device()
    print(f"Hardware: {device}")
    if device in ("cuda", "mps"):
        print(f"  Accelerated: YES ({device})")
    else:
        print("  Accelerated: NO (CPU only)")
        print("  Note: CUDA/MPS not detected. OpenVINO/RKNN not yet supported.")
        print("  See: docs/superpowers/specs/2026-07-09-v0.3.0-remote-asr-embedding-node-design.md")

    print()
    print("ASR models:")
    asr_models = check_asr_models()
    for model_id, present in asr_models.items():
        status = "INSTALLED" if present else "MISSING"
        print(f"  [{status}] {model_id}")

    print()
    print("Embedding models:")
    emb_models = check_embedding_models()
    for model_id, present in emb_models.items():
        status = "INSTALLED" if present else "MISSING"
        print(f"  [{status}] {model_id}")


def cmd_deploy() -> None:
    """Probe + build isolated venvs + deploy missing models."""
    device = detect_best_device()
    print(f"Detected device: {device}")
    print()

    print("Preparing isolated toolchain (uv + Python 3.12 + venvs)...")
    _ensure_uv()
    _ensure_python_312()
    _create_venvs()
    print()

    asr_models = check_asr_models()
    all_asr_ok = all(asr_models.values())
    if all_asr_ok:
        print("ASR models: all present, skipping deploy.")
    else:
        print("ASR models: deploying...")
        deploy_asr(device)

    print()

    emb_models = check_embedding_models()
    all_emb_ok = all(emb_models.values())
    if all_emb_ok:
        print("Embedding models: all present, skipping deploy.")
    else:
        print("Embedding models: deploying...")
        deploy_embedding(device)

    print()
    print("Deploy complete.")


def _cleanup_procs(procs: list) -> None:
    """Terminate all child processes and wait for them to exit."""
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


def cmd_serve() -> None:
    """Start both services."""
    device = detect_best_device()
    print(f"Starting services (device={device})...")

    procs = []

    # Check if already running
    if check_health(ASR_PORT):
        print(f"  ASR service already running on port {ASR_PORT}")
    else:
        print(f"  Starting ASR service on port {ASR_PORT}...")
        asr_proc = start_asr(device)
        procs.append(asr_proc)
        if not wait_for_health(ASR_PORT):
            print(f"  ERROR: ASR service failed to start on port {ASR_PORT}")
            _cleanup_procs(procs)
            sys.exit(1)
        print(f"  ASR service ready on port {ASR_PORT}")

    if check_health(EMBEDDING_PORT):
        print(f"  Embedding service already running on port {EMBEDDING_PORT}")
    else:
        print(f"  Starting embedding service on port {EMBEDDING_PORT}...")
        emb_proc = start_embedding(device)
        procs.append(emb_proc)
        if not wait_for_health(EMBEDDING_PORT):
            print(f"  ERROR: Embedding service failed to start on port {EMBEDDING_PORT}")
            _cleanup_procs(procs)
            sys.exit(1)
        print(f"  Embedding service ready on port {EMBEDDING_PORT}")

    lan_ip = get_lan_ip()
    print()
    print("=" * 60)
    print("  Services running. Configure Memento Settings:")
    print()
    print(f"  ASR endpoint:       http://{lan_ip}:{ASR_PORT}/v1")
    print(f"  Embedding endpoint: http://{lan_ip}:{EMBEDDING_PORT}/v1")
    print()
    print("  In Memento Settings, create presets with these endpoints.")
    print("  Provider: cloud (for embedding) or local (for ASR)")
    print("=" * 60)
    print()
    print("Press Ctrl+C to stop all services.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        _cleanup_procs(procs)


def cmd_run() -> None:
    """Deploy + serve in one shot."""
    cmd_deploy()
    print()
    cmd_serve()


# ---------------------------------------------------------------------------
# Interactive menu (stdlib only: termios/tty on Unix, msvcrt on Windows)
# ---------------------------------------------------------------------------

_MENU_ITEMS = [
    "查看状态（硬件 + 模型）",
    "部署环境（建 venv + 下载模型）",
    "启动服务",
    "一键部署并启动",
    "退出",
]


def _render_menu(title: str, options: list[str], selected: int) -> None:
    """Clear screen and draw the menu, highlighting the selected line."""
    sys.stdout.write("\033[2J\033[H")  # clear screen + cursor home
    sys.stdout.write(f"{title}\n\n")
    for i, opt in enumerate(options):
        if i == selected:
            sys.stdout.write(f"\033[7m> {opt}\033[0m\n")  # inverted video
        else:
            sys.stdout.write(f"  {opt}\n")
    sys.stdout.write("\n(↑/↓ 选择，Enter 确认，Ctrl+C 退出)\n")
    sys.stdout.flush()


def _read_key_unix() -> str:
    """Read one logical key on Unix (termios/tty + select for ESC disambiguation)."""
    import select
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":  # ESC — arrow keys send ESC [ A / ESC [ B
            ready, _, _ = select.select([sys.stdin], [], [], 0.1)
            if not ready:
                return "esc"  # lone ESC (no follow-up bytes)
            seq = sys.stdin.read(2)
            if seq == "[A":
                return "up"
            if seq == "[B":
                return "down"
            return "esc"
        if ch in ("\r", "\n"):
            return "enter"
        if ch == "\x03":  # Ctrl-C
            raise KeyboardInterrupt
        return "other"
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _read_key_windows() -> str:
    """Read one logical key on Windows (msvcrt)."""
    import msvcrt
    ch = msvcrt.getch()
    if ch in (b"\x00", b"\xe0"):  # special-key prefix (arrows, etc.)
        ch2 = msvcrt.getch()
        if ch2 == b"H":
            return "up"
        if ch2 == b"P":
            return "down"
        return "other"
    if ch == b"\x1b":  # ESC
        return "esc"
    if ch in (b"\r", b"\n"):
        return "enter"
    if ch == b"\x03":  # Ctrl-C
        raise KeyboardInterrupt
    return "other"


def _select_menu(title: str, options: list[str]) -> int:
    """Interactive arrow-key menu. Returns the selected index, or -1 if cancelled."""
    read_key = _read_key_windows if sys.platform == "win32" else _read_key_unix
    selected = 0
    _render_menu(title, options, selected)
    try:
        while True:
            key = read_key()
            if key == "up":
                selected = (selected - 1) % len(options)
            elif key == "down":
                selected = (selected + 1) % len(options)
            elif key == "enter":
                sys.stdout.write("\033[0m\n")
                sys.stdout.flush()
                return selected
            elif key == "esc":
                sys.stdout.write("\n")
                return -1
            _render_menu(title, options, selected)
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        return -1


def _interactive() -> None:
    """Run the interactive menu loop."""
    actions = {0: cmd_probe, 1: cmd_deploy, 2: cmd_serve, 3: cmd_run}
    while True:
        choice = _select_menu("Memento 远程节点", _MENU_ITEMS)
        if choice in (-1, 4):  # cancelled or "退出"
            print("Bye.")
            return
        actions[choice]()
        # Let the user read probe/deploy output before the menu clears the screen.
        if choice in (0, 1):
            try:
                input("\n按 Enter 返回菜单 (Ctrl+C 退出) ...")
            except KeyboardInterrupt:
                print("\nBye.")
                return


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

_COMMANDS = {
    "probe": cmd_probe,
    "deploy": cmd_deploy,
    "serve": cmd_serve,
    "run": cmd_run,
}


def main() -> None:
    """If a known command is given as argv[1], run it directly; else show the menu.

    Keeps scripts/CI working (`python bootstrap.py probe`) while making the
    no-arg path an interactive menu.
    """
    if len(sys.argv) > 1 and sys.argv[1] in _COMMANDS:
        _COMMANDS[sys.argv[1]]()
        return
    _interactive()


if __name__ == "__main__":
    main()
