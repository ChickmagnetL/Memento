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


# ---------------------------------------------------------------------------
# Original deploy tests (backward compat)
# ---------------------------------------------------------------------------


def test_deploy_creates_venv_installs_requirements_and_models(monkeypatch, tmp_path: Path):
    deploy_module = load_deploy_module()
    commands = []
    progress = []
    model_downloads = []
    venv_dir = tmp_path / ".venv"

    def fake_run_command(args, cwd=None, env=None):
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
        "environment",
        "models",
        "done",
    ]


def test_torch_command_selects_platform_specific_wheel(monkeypatch, tmp_path: Path):
    deploy_module = load_deploy_module()
    monkeypatch.setattr(deploy_module, "VENV_DIR", tmp_path / ".venv")

    # use_cuda=False -> base command, no CUDA index-url
    assert deploy_module.torch_install_command(use_cuda=False) == [
        str(deploy_module.python_bin()),
        "-m",
        "pip",
        "install",
        "torch",
        "torchaudio",
    ]
    assert "--index-url" not in deploy_module.torch_install_command(use_cuda=False)

    # use_cuda=True -> CUDA index-url appended
    assert deploy_module.torch_install_command(use_cuda=True)[-2:] == [
        "--index-url",
        "https://download.pytorch.org/whl/cu121",
    ]


def test_download_models_invokes_sensevoice_and_moonshine(monkeypatch):
    deploy_module = load_deploy_module()
    commands = []
    envs = []
    progress = []

    def fake_run_command(args, cwd=None, env=None):
        commands.append(args)
        envs.append(env)

    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)

    deploy_module.download_models(
        Path("/venv/bin/python"),
        on_progress=lambda stage, detail, percent=None: progress.append((stage, detail, percent)),
    )

    joined = [" ".join(str(a) for a in cmd) for cmd in commands]
    assert any("snapshot_download" in c and "iic/SenseVoiceSmall" in c for c in joined)
    assert any("moonshine_voice" in c for c in joined)
    # Moonshine command injects MOONSHINE_VOICE_CACHE env pointing at the moonshine cache dir
    assert any(
        e and e.get("MOONSHINE_VOICE_CACHE") == str(deploy_module.MOONSHINE_CACHE_DIR)
        for e in envs
    )
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


# ---------------------------------------------------------------------------
# Task 3: ensure_environment (venv + deps, no model download)
# ---------------------------------------------------------------------------


def test_ensure_environment_does_not_download_models(monkeypatch, tmp_path: Path):
    """ensure_environment creates venv + deps + torch but does NOT download models."""
    deploy_module = load_deploy_module()
    commands = []
    progress = []
    venv_dir = tmp_path / ".venv"

    def fake_run_command(args, cwd=None, env=None):
        commands.append(args)
        if args[:3] == [sys.executable, "-m", "venv"]:
            venv_dir.mkdir()

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)

    deploy_module.ensure_environment(
        on_progress=lambda stage, detail, percent=None: progress.append((stage, detail, percent)),
    )

    joined = [" ".join(str(a) for a in cmd) for cmd in commands]
    # Should have venv creation
    assert any("venv" in c for c in joined)
    # Should have pip install requirements
    assert any("requirements.txt" in c for c in joined)
    # Should have torch install
    assert any("torch" in c for c in joined)
    # Should NOT have any model download commands
    assert not any("AutoModel" in c for c in joined)
    assert not any("moonshine_voice" in c for c in joined)
    assert not any("get_model_for_language" in c for c in joined)

    stages = [stage for stage, _detail, _percent in progress]
    assert "venv" in stages
    assert "dependencies" in stages
    assert "torch" in stages
    assert "environment" in stages
    # No "models" stage
    assert "models" not in stages


def test_ensure_environment_cleans_partial_venv_on_failure(monkeypatch, tmp_path: Path):
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
        deploy_module.ensure_environment()
    except RuntimeError as exc:
        assert "pip failed" in str(exc)
    else:
        raise AssertionError("expected ensure_environment failure")

    assert not venv_dir.exists()


# ---------------------------------------------------------------------------
# Task 3: download_model (single model)
# ---------------------------------------------------------------------------


def test_download_model_sensevoice_small(monkeypatch):
    """download_model with sensevoice runtime triggers iic/SenseVoiceSmall import."""
    deploy_module = load_deploy_module()
    commands = []
    progress = []

    monkeypatch.setattr(deploy_module, "run_command", lambda args, cwd=None, env=None: commands.append(args))

    deploy_module.download_model(
        Path("/venv/bin/python"),
        model_id="iic/SenseVoiceSmall",
        runtime="sensevoice",
        on_progress=lambda stage, detail, percent=None: progress.append((stage, detail, percent)),
    )

    joined = [" ".join(str(a) for a in cmd) for cmd in commands]
    assert len(joined) == 1
    assert "snapshot_download" in joined[0]
    assert "iic/SenseVoiceSmall" in joined[0]
    assert "models/sensevoice" in joined[0]
    # Should NOT contain any moonshine imports
    assert "moonshine_voice" not in joined[0]

    assert progress == [
        ("models", "Downloading iic/SenseVoiceSmall", 50),
        ("models", "Downloaded iic/SenseVoiceSmall", 100),
    ]


def test_download_model_moonshine_tiny_en(monkeypatch):
    """download_model with moonshine tiny-en triggers TINY ModelArch + MOONSHINE_VOICE_CACHE env."""
    deploy_module = load_deploy_module()
    commands = []
    envs = []
    progress = []

    def fake_run_command(args, cwd=None, env=None):
        commands.append(args)
        envs.append(env)

    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)

    deploy_module.download_model(
        Path("/venv/bin/python"),
        model_id="moonshine_voice/tiny-en",
        runtime="moonshine",
        spec="tiny-en",
        on_progress=lambda stage, detail, percent=None: progress.append((stage, detail, percent)),
    )

    joined = [" ".join(str(a) for a in cmd) for cmd in commands]
    assert len(joined) == 1
    assert "moonshine_voice" in joined[0]
    assert "ModelArch.TINY" in joined[0]
    # Should NOT contain any funasr imports
    assert "AutoModel" not in joined[0]
    assert "funasr" not in joined[0]
    # MOONSHINE_VOICE_CACHE env injected, pointing at the moonshine cache dir
    assert envs[0] is not None
    assert envs[0]["MOONSHINE_VOICE_CACHE"] == str(deploy_module.MOONSHINE_CACHE_DIR)


def test_download_model_moonshine_base_en(monkeypatch):
    """download_model with moonshine base-en triggers BASE ModelArch."""
    deploy_module = load_deploy_module()
    commands = []

    monkeypatch.setattr(deploy_module, "run_command", lambda args, cwd=None, env=None: commands.append(args))

    deploy_module.download_model(
        Path("/venv/bin/python"),
        model_id="moonshine_voice/base-en",
        runtime="moonshine",
        spec="base-en",
    )

    joined = [" ".join(str(a) for a in cmd) for cmd in commands]
    assert "ModelArch.BASE" in joined[0]


def test_download_model_moonshine_tiny_streaming(monkeypatch):
    """download_model with tiny-streaming-en triggers TINY_STREAMING ModelArch."""
    deploy_module = load_deploy_module()
    commands = []

    monkeypatch.setattr(deploy_module, "run_command", lambda args, cwd=None, env=None: commands.append(args))

    deploy_module.download_model(
        Path("/venv/bin/python"),
        model_id="moonshine_voice/tiny-streaming-en",
        runtime="moonshine",
        spec="tiny-streaming-en",
    )

    joined = [" ".join(str(a) for a in cmd) for cmd in commands]
    assert "ModelArch.TINY_STREAMING" in joined[0]


def test_download_model_moonshine_small_streaming(monkeypatch):
    """download_model with small-streaming-en triggers SMALL_STREAMING ModelArch."""
    deploy_module = load_deploy_module()
    commands = []

    monkeypatch.setattr(deploy_module, "run_command", lambda args, cwd=None, env=None: commands.append(args))

    deploy_module.download_model(
        Path("/venv/bin/python"),
        model_id="moonshine_voice/small-streaming-en",
        runtime="moonshine",
        spec="small-streaming-en",
    )

    joined = [" ".join(str(a) for a in cmd) for cmd in commands]
    assert "ModelArch.SMALL_STREAMING" in joined[0]


def test_download_model_moonshine_medium_streaming(monkeypatch):
    """download_model with medium-streaming-en triggers MEDIUM_STREAMING ModelArch."""
    deploy_module = load_deploy_module()
    commands = []

    monkeypatch.setattr(deploy_module, "run_command", lambda args, cwd=None, env=None: commands.append(args))

    deploy_module.download_model(
        Path("/venv/bin/python"),
        model_id="moonshine_voice/medium-streaming-en",
        runtime="moonshine",
        spec="medium-streaming-en",
    )

    joined = [" ".join(str(a) for a in cmd) for cmd in commands]
    assert "ModelArch.MEDIUM_STREAMING" in joined[0]


def test_download_model_unknown_runtime_raises(monkeypatch):
    """download_model with unknown runtime raises ValueError."""
    deploy_module = load_deploy_module()
    commands = []

    monkeypatch.setattr(deploy_module, "run_command", lambda args, cwd=None, env=None: commands.append(args))

    try:
        deploy_module.download_model(
            Path("/venv/bin/python"),
            model_id="unknown/model",
            runtime="unknown_runtime",
        )
    except ValueError as exc:
        assert "Unknown runtime" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_download_model_unknown_moonshine_spec_raises(monkeypatch):
    """download_model with unknown moonshine spec raises ValueError."""
    deploy_module = load_deploy_module()
    commands = []

    monkeypatch.setattr(deploy_module, "run_command", lambda args, cwd=None, env=None: commands.append(args))

    try:
        deploy_module.download_model(
            Path("/venv/bin/python"),
            model_id="moonshine_voice/unknown",
            runtime="moonshine",
            spec="unknown-spec",
        )
    except ValueError as exc:
        assert "Unknown moonshine spec" in str(exc)
    else:
        raise AssertionError("expected ValueError")


# ---------------------------------------------------------------------------
# Task 3: install_model (ensure_environment + download_model)
# ---------------------------------------------------------------------------


def test_install_model_moonshine_tiny_en_only_downloads_tiny_en(monkeypatch, tmp_path: Path):
    """install_model('moonshine-tiny-en') only triggers tiny-en, not other models."""
    deploy_module = load_deploy_module()
    commands = []
    progress = []
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()  # pre-create to avoid venv creation step
    # Also create python bin
    bin_dir = venv_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "python").touch()

    def fake_run_command(args, cwd=None, env=None):
        commands.append(args)

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)

    deploy_module.install_model(
        slug="moonshine-tiny-en",
        model_id="moonshine_voice/tiny-en",
        runtime="moonshine",
        spec="tiny-en",
        on_progress=lambda stage, detail, percent=None: progress.append((stage, detail, percent)),
    )

    joined = [" ".join(str(a) for a in cmd) for cmd in commands]
    # Should have ONE model download command
    model_commands = [c for c in joined if "moonshine_voice" in c or "AutoModel" in c]
    assert len(model_commands) == 1
    assert "ModelArch.TINY" in model_commands[0]
    # Should NOT trigger SenseVoice download
    assert not any("iic/SenseVoiceSmall" in c for c in joined)
    assert not any("AutoModel" in c for c in joined)

    # Progress should end with done
    stages = [stage for stage, _detail, _percent in progress]
    assert stages[-1] == "done"


def test_install_model_sensevoice_small_only_triggers_sensevoice(monkeypatch, tmp_path: Path):
    """install_model('sensevoice-small') only triggers SenseVoiceSmall, not moonshine."""
    deploy_module = load_deploy_module()
    commands = []
    progress = []
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    bin_dir = venv_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "python").touch()

    def fake_run_command(args, cwd=None, env=None):
        commands.append(args)

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)

    deploy_module.install_model(
        slug="sensevoice-small",
        model_id="iic/SenseVoiceSmall",
        runtime="sensevoice",
        on_progress=lambda stage, detail, percent=None: progress.append((stage, detail, percent)),
    )

    joined = [" ".join(str(a) for a in cmd) for cmd in commands]
    # Should have ONE model download command
    model_commands = [c for c in joined if "snapshot_download" in c or "moonshine_voice" in c]
    assert len(model_commands) == 1
    assert "iic/SenseVoiceSmall" in model_commands[0]
    # Should NOT trigger any moonshine download
    assert not any("moonshine_voice" in c for c in joined)
    assert not any("ModelArch" in c for c in joined)


# ---------------------------------------------------------------------------
# Task 3: uninstall_model / uninstall_all
# ---------------------------------------------------------------------------


def test_uninstall_model_removes_specific_cache(monkeypatch, tmp_path: Path):
    """uninstall_model removes only the given cache path."""
    deploy_module = load_deploy_module()

    cache_dir = tmp_path / "model_cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "model.bin").touch()

    monkeypatch.setattr(deploy_module, "VENV_DIR", tmp_path / ".venv")

    deploy_module.uninstall_model(str(cache_dir))

    assert not cache_dir.exists()


def test_uninstall_all_removes_caches_and_venv(monkeypatch, tmp_path: Path):
    """uninstall_all removes all model caches + .venv."""
    deploy_module = load_deploy_module()

    cache1 = tmp_path / "cache1"
    cache1.mkdir(parents=True)
    (cache1 / "model.bin").touch()

    cache2 = tmp_path / "cache2"
    cache2.mkdir(parents=True)
    (cache2 / "model.bin").touch()

    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir(parents=True)
    (venv_dir / "bin" / "python").parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)

    deploy_module.uninstall_all([str(cache1), str(cache2)])

    assert not cache1.exists()
    assert not cache2.exists()
    assert not venv_dir.exists()


def test_uninstall_all_does_not_remove_unknown_parent_dirs(monkeypatch, tmp_path: Path):
    """uninstall_all removes the venv and caches but not unknown parent cache dirs."""
    deploy_module = load_deploy_module()

    # Create a cache structure where the parent is something like ~/.cache/huggingface/hub
    parent_dir = tmp_path / ".cache" / "huggingface" / "hub"
    cache_dir = parent_dir / "models--moonshine_voice--tiny-en"
    cache_dir.mkdir(parents=True)
    (cache_dir / "model.bin").touch()

    # Create another sibling dir that represents an "unknown" cache
    unknown_dir = parent_dir / "models--some_other_model"
    unknown_dir.mkdir(parents=True, exist_ok=True)
    (unknown_dir / "other.bin").touch()

    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir(parents=True)

    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)

    deploy_module.uninstall_all([str(cache_dir)])

    # The known cache should be removed
    assert not cache_dir.exists()
    # The venv should be removed
    assert not venv_dir.exists()
    # But the unknown sibling dir and parent dirs should still exist
    assert unknown_dir.exists()
    assert parent_dir.exists()
