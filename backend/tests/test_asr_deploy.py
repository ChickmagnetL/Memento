"""Tests for the ASR service deployer."""

import importlib.util
import sys
from pathlib import Path


DEPLOY_PATH = Path(__file__).resolve().parents[2] / "services" / "asr" / "deploy.py"


def load_deploy_module():
    spec = importlib.util.spec_from_file_location("asr_deploy_test", DEPLOY_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_deploy_creates_venv_installs_requirements_and_models(monkeypatch, tmp_path: Path):
    deploy_module = load_deploy_module()
    commands = []
    progress = []
    model_downloads = []
    venv_dir = tmp_path / ".venv"

    def fake_run_command(args, cwd=None):
        commands.append(args)
        if args[:3] == [sys.executable, "-m", "venv"]:
            venv_dir.mkdir()

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)
    monkeypatch.setattr(
        deploy_module,
        "download_models",
        lambda python, on_progress: model_downloads.append(python),
    )

    deploy_module.deploy(on_progress=lambda stage, detail, percent=None: progress.append((stage, detail, percent)))

    assert [sys.executable, "-m", "venv", str(venv_dir)] in commands
    assert any("requirements.txt" in command for command in commands for command in command)
    assert model_downloads == [deploy_module.python_bin()]
    assert [stage for stage, _detail, _percent in progress] == [
        "venv",
        "dependencies",
        "torch",
        "models",
        "done",
    ]


def test_torch_command_selects_platform_specific_wheel(monkeypatch, tmp_path: Path):
    deploy_module = load_deploy_module()
    monkeypatch.setattr(deploy_module, "VENV_DIR", tmp_path / ".venv")

    monkeypatch.setattr(deploy_module.sys, "platform", "darwin")
    assert deploy_module.torch_install_command(device=None) == [
        str(deploy_module.python_bin()),
        "-m",
        "pip",
        "install",
        "torch",
        "torchaudio",
    ]

    monkeypatch.setattr(deploy_module.sys, "platform", "linux")
    monkeypatch.setattr(deploy_module, "has_nvidia_gpu", lambda: True)
    assert deploy_module.torch_install_command(device=None)[-2:] == [
        "--index-url",
        "https://download.pytorch.org/whl/cu121",
    ]

    monkeypatch.setattr(deploy_module.sys, "platform", "win32")
    assert deploy_module.torch_install_command(device="cuda")[-2:] == [
        "--index-url",
        "https://download.pytorch.org/whl/cu121",
    ]

    monkeypatch.setattr(deploy_module.sys, "platform", "linux")
    monkeypatch.setattr(deploy_module, "has_nvidia_gpu", lambda: False)
    assert "--index-url" not in deploy_module.torch_install_command(device=None)


def test_download_models_invokes_sensevoice_and_moonshine(monkeypatch):
    deploy_module = load_deploy_module()
    commands = []
    progress = []

    monkeypatch.setattr(
        deploy_module,
        "run_command",
        lambda args, cwd=None: commands.append(args),
    )

    deploy_module.download_models(
        Path("/venv/bin/python"),
        on_progress=lambda stage, detail, percent=None: progress.append((stage, detail, percent)),
    )

    joined = [" ".join(command) for command in commands]
    assert any("AutoModel" in command and "iic/SenseVoiceSmall" in command for command in joined)
    assert any("moonshine_voice" in command for command in joined)
    assert progress == [
        ("models", "Downloading SenseVoiceSmall", 50),
        ("models", "Downloading Moonshine Voice", 90),
    ]


def test_deploy_cleans_partial_venv_on_failure(monkeypatch, tmp_path: Path):
    deploy_module = load_deploy_module()
    venv_dir = tmp_path / ".venv"

    def fake_run_command(args, cwd=None):
        if args[:3] == [sys.executable, "-m", "venv"]:
            venv_dir.mkdir()
            return
        raise RuntimeError("pip failed")

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)

    try:
        deploy_module.deploy()
    except RuntimeError as exc:
        assert "pip failed" in str(exc)
    else:
        raise AssertionError("expected deploy failure")

    assert not venv_dir.exists()


def test_run_script_binds_all_interfaces():
    run_script = DEPLOY_PATH.parent / "run.sh"

    assert "--host" in run_script.read_text(encoding="utf-8")
    assert "0.0.0.0" in run_script.read_text(encoding="utf-8")
    assert "server:app" in run_script.read_text(encoding="utf-8")
