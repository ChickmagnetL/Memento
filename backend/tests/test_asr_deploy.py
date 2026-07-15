"""Tests for the ASR service deployer."""

import importlib.util
import subprocess
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


def test_pip_index_candidates_default_custom_and_empty(monkeypatch):
    deploy_module = load_deploy_module()

    monkeypatch.setattr(deploy_module, "_USER_PIP_INDEX_URL", None)
    assert deploy_module._pip_index_candidates() == [
        "https://pypi.tuna.tsinghua.edu.cn/simple",
        "https://mirrors.aliyun.com/pypi/simple/",
        "https://pypi.org/simple",
    ]

    monkeypatch.setattr(deploy_module, "_USER_PIP_INDEX_URL", "https://pip.example/simple")
    assert deploy_module._pip_index_candidates() == ["https://pip.example/simple"]

    monkeypatch.setattr(deploy_module, "_USER_PIP_INDEX_URL", "   ")
    assert deploy_module._pip_index_candidates() == [None]


def test_run_pip_falls_back_in_order(monkeypatch):
    deploy_module = load_deploy_module()
    monkeypatch.setattr(deploy_module, "_USER_PIP_INDEX_URL", None)
    commands = []

    def fake_run_command(args, cwd=None, env=None):
        commands.append(list(args))
        if len(commands) < 3:
            raise RuntimeError("index unavailable")

    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)
    deploy_module._run_pip_with_fallback(["python", "-m", "pip", "install", "demo"])

    assert [command[-1] for command in commands] == [
        "https://pypi.tuna.tsinghua.edu.cn/simple",
        "https://mirrors.aliyun.com/pypi/simple/",
        "https://pypi.org/simple",
    ]


def test_run_command_includes_bounded_process_output(monkeypatch):
    deploy_module = load_deploy_module()

    def fake_subprocess_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args[0], 1, stdout="install context", stderr="x" * 5_000 + "root cause"
        )

    monkeypatch.setattr(deploy_module.subprocess, "run", fake_subprocess_run)

    try:
        deploy_module.run_command(["python", "-m", "pip", "install", "demo"])
    except RuntimeError as exc:
        message = str(exc)
        assert "exit code 1" in message
        assert "root cause" in message
        assert "output truncated" in message
        assert len(message) < 5_500
    else:
        raise AssertionError("expected a command failure")


# ---------------------------------------------------------------------------
# Original deploy tests (backward compat)
# ---------------------------------------------------------------------------


def test_deploy_creates_venv_installs_requirements_and_models(monkeypatch, tmp_path: Path):
    deploy_module = load_deploy_module()
    commands = []
    progress = []
    model_downloads = []
    venv_dir = tmp_path / ".venv"
    models_dir = tmp_path / "models"

    def fake_run_command(args, cwd=None, env=None):
        commands.append(args)
        if args[:3] == [sys.executable, "-m", "venv"]:
            venv_dir.mkdir()

    def fake_sensevoice(python, model_id, cache_dir):
        model_downloads.append(("sensevoice", python, model_id))

    def fake_moonshine(python, arch, *, label):
        model_downloads.append(("moonshine", python, arch, label))

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "MODELS_DIR", models_dir)
    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)
    monkeypatch.setattr(deploy_module, "_run_sensevoice_download", fake_sensevoice)
    monkeypatch.setattr(deploy_module, "_run_moonshine_download", fake_moonshine)

    deploy_module.deploy(on_progress=lambda stage, detail, percent=None: progress.append((stage, detail, percent)))

    assert [sys.executable, "-m", "venv", str(venv_dir)] in commands
    assert any("requirements.txt" in command for command in commands for command in command)
    assert model_downloads == [
        ("sensevoice", deploy_module.python_bin(), "iic/SenseVoiceSmall"),
        ("moonshine", deploy_module.python_bin(), "MEDIUM_STREAMING", "Moonshine Voice"),
    ]
    stages = [stage for stage, _detail, _percent in progress]
    assert stages[:4] == [
        "venv",
        "dependencies",
        "torch",
        "environment",
    ]
    assert "models" in stages
    assert stages[-1] == "done"


def test_deploy_skips_model_download_when_present(monkeypatch, tmp_path: Path):
    """deploy always ensures env, but skips downloads when both models are cached."""
    deploy_module = load_deploy_module()
    commands = []
    model_downloads = []
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    models_dir = tmp_path / "models"
    # SenseVoice present
    sense_pt = models_dir / "sensevoice" / "iic" / "SenseVoiceSmall" / "model.pt"
    sense_pt.parent.mkdir(parents=True)
    sense_pt.touch()
    # Moonshine present
    moon_dir = (
        models_dir
        / "moonshine"
        / "download.moonshine.ai"
        / "model"
        / "medium-streaming-en"
        / "quantized"
    )
    moon_dir.mkdir(parents=True)
    (tmp_path / "requirements.txt").write_text("")

    def fake_run_command(args, cwd=None, env=None):
        commands.append(args)

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "MODELS_DIR", models_dir)
    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)
    monkeypatch.setattr(
        deploy_module,
        "_run_sensevoice_download",
        lambda *a, **k: model_downloads.append("sensevoice"),
    )
    monkeypatch.setattr(
        deploy_module,
        "_run_moonshine_download",
        lambda *a, **k: model_downloads.append("moonshine"),
    )

    deploy_module.deploy(device="cpu")

    # env repair still ran (pip / torch)
    joined = [" ".join(str(a) for a in c) for c in commands]
    assert any("requirements.txt" in c for c in joined)
    assert any("torch" in c for c in joined)
    assert model_downloads == []


def test_deploy_downloads_only_missing_models(monkeypatch, tmp_path: Path):
    """When only SenseVoice is missing, only that download runs."""
    deploy_module = load_deploy_module()
    model_downloads = []
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    models_dir = tmp_path / "models"
    # Only moonshine present
    moon_dir = (
        models_dir
        / "moonshine"
        / "download.moonshine.ai"
        / "model"
        / "medium-streaming-en"
        / "quantized"
    )
    moon_dir.mkdir(parents=True)
    (tmp_path / "requirements.txt").write_text("")

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "MODELS_DIR", models_dir)
    monkeypatch.setattr(deploy_module, "run_command", lambda *a, **k: None)
    monkeypatch.setattr(
        deploy_module,
        "_run_sensevoice_download",
        lambda *a, **k: model_downloads.append("sensevoice"),
    )
    monkeypatch.setattr(
        deploy_module,
        "_run_moonshine_download",
        lambda *a, **k: model_downloads.append("moonshine"),
    )

    deploy_module.deploy(device="cpu")

    assert model_downloads == ["sensevoice"]


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

    # use_cuda=True -> CUDA index-url appended.
    # cu124 (not cu121): the cu121 index tops out at torch 2.5.1, but torch.load
    # requires >= 2.6 since CVE-2025-32434, which ASR model weights hit.
    assert deploy_module.torch_install_command(use_cuda=True)[-2:] == [
        "--index-url",
        "https://download.pytorch.org/whl/cu124",
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
    assert any("snapshot_download" in c for c in joined)
    # SenseVoice model_id + cache dir are passed via env vars (not interpolated
    # into the script string, which would mangle Windows backslash paths).
    assert any(
        e and e.get("MEM_DOWNLOAD_MODEL_ID") == "iic/SenseVoiceSmall" for e in envs
    )
    assert any(
        e and e.get("MEM_DOWNLOAD_CACHE_DIR")
        == str(deploy_module.SENSEVOICE_CACHE_DIR)
        for e in envs
    )
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


def test_frozen_environment_uses_managed_toolchain(monkeypatch, tmp_path: Path):
    deploy_module = load_deploy_module()
    venv_dir = tmp_path / ".venv"
    managed_calls = []
    commands = []

    def fake_ensure_managed_toolchain():
        managed_calls.append(True)
        venv_dir.mkdir()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(
        deploy_module,
        "_ensure_managed_toolchain",
        fake_ensure_managed_toolchain,
    )
    monkeypatch.setattr(
        deploy_module,
        "run_command",
        lambda args, cwd=None, env=None: commands.append(args),
    )

    deploy_module.ensure_environment(device="cpu")

    assert managed_calls == [True]
    assert [sys.executable, "-m", "venv", str(venv_dir)] not in commands


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
    envs = []
    progress = []

    def fake_run_command(args, cwd=None, env=None):
        commands.append(args)
        envs.append(env)

    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)

    deploy_module.download_model(
        Path("/venv/bin/python"),
        model_id="iic/SenseVoiceSmall",
        runtime="sensevoice",
        on_progress=lambda stage, detail, percent=None: progress.append((stage, detail, percent)),
    )

    joined = [" ".join(str(a) for a in cmd) for cmd in commands]
    assert len(joined) == 1
    assert "snapshot_download" in joined[0]
    # model_id and cache dir are passed via env, not interpolated into the
    # script (avoids Windows backslash mangling).
    assert "iic/SenseVoiceSmall" not in joined[0]
    assert "models/sensevoice" not in joined[0]
    assert envs[0] is not None
    assert envs[0]["MEM_DOWNLOAD_MODEL_ID"] == "iic/SenseVoiceSmall"
    assert envs[0]["MEM_DOWNLOAD_CACHE_DIR"] == str(deploy_module.SENSEVOICE_CACHE_DIR)
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


def test_download_model_moonshine_disables_xet(monkeypatch):
    """Moonshine (HF) download env forces HF_HUB_DISABLE_XET=1.

    With hf_xet installed, HF routes large LFS files through the xet native
    protocol which stalls at 0 bytes/s on this network; the HTTP bridge (~9 MB/s)
    is selected by disabling xet.
    """
    deploy_module = load_deploy_module()
    envs = []

    def fake_run_command(args, cwd=None, env=None):
        envs.append(env)

    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)

    deploy_module.download_model(
        Path("/venv/bin/python"),
        model_id="moonshine_voice/tiny-en",
        runtime="moonshine",
        spec="tiny-en",
    )

    assert envs
    assert envs[0]["HF_HUB_DISABLE_XET"] == "1"


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
    envs = []
    progress = []
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    bin_dir = venv_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "python").touch()

    def fake_run_command(args, cwd=None, env=None):
        commands.append(args)
        envs.append(env)

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
    # model_id is passed via env (not interpolated into the script string,
    # which would mangle Windows backslash paths).
    assert any(
        e and e.get("MEM_DOWNLOAD_MODEL_ID") == "iic/SenseVoiceSmall" for e in envs
    )
    # Should NOT trigger any moonshine download
    assert not any("moonshine_voice" in c for c in joined)
    assert not any("ModelArch" in c for c in joined)


# ---------------------------------------------------------------------------
# HF endpoint fallback (Moonshine download)
# ---------------------------------------------------------------------------


def test_hf_endpoint_candidates_default_order(monkeypatch):
    deploy_module = load_deploy_module()
    monkeypatch.setattr(deploy_module, "_USER_HF_ENDPOINT", None)
    assert deploy_module._hf_endpoint_candidates() == [
        "https://huggingface.co",
        "https://hf-mirror.com",
    ]


def test_hf_endpoint_candidates_known_user_prefers_then_fallback(monkeypatch):
    deploy_module = load_deploy_module()
    monkeypatch.setattr(deploy_module, "_USER_HF_ENDPOINT", "https://huggingface.co")
    assert deploy_module._hf_endpoint_candidates() == [
        "https://huggingface.co",
        "https://hf-mirror.com",
    ]


def test_hf_endpoint_candidates_custom_is_exclusive(monkeypatch):
    deploy_module = load_deploy_module()
    monkeypatch.setattr(deploy_module, "_USER_HF_ENDPOINT", "https://hf.example.internal")
    assert deploy_module._hf_endpoint_candidates() == ["https://hf.example.internal"]


def test_download_model_moonshine_falls_back_to_second_endpoint(monkeypatch):
    """Moonshine download tries mirror first, then official on failure."""
    deploy_module = load_deploy_module()
    monkeypatch.setattr(deploy_module, "_USER_HF_ENDPOINT", None)
    endpoints = []

    def fake_run_command(args, cwd=None, env=None):
        endpoint = env.get("HF_ENDPOINT") if env else None
        endpoints.append(endpoint)
        assert env and env.get("MOONSHINE_VOICE_CACHE") == str(deploy_module.MOONSHINE_CACHE_DIR)
        if endpoint == "https://huggingface.co":
            raise RuntimeError("could not connect to huggingface.co")

    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)

    deploy_module.download_model(
        Path("/venv/bin/python"),
        model_id="moonshine_voice/tiny-en",
        runtime="moonshine",
        spec="tiny-en",
    )

    assert endpoints == [
        "https://huggingface.co",
        "https://hf-mirror.com",
    ]


def test_download_model_moonshine_raises_when_all_endpoints_fail(monkeypatch):
    deploy_module = load_deploy_module()
    monkeypatch.setattr(deploy_module, "_USER_HF_ENDPOINT", None)

    def fake_run_command(args, cwd=None, env=None):
        raise RuntimeError(f"down ({env.get('HF_ENDPOINT')})")

    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)

    try:
        deploy_module.download_model(
            Path("/venv/bin/python"),
            model_id="moonshine_voice/tiny-en",
            runtime="moonshine",
            spec="tiny-en",
        )
    except RuntimeError as exc:
        msg = str(exc)
        assert "all HF endpoints" in msg
        assert "https://hf-mirror.com" in msg
        assert "https://huggingface.co" in msg
    else:
        raise AssertionError("expected RuntimeError when all endpoints fail")


def test_download_model_sensevoice_does_not_retry_hf_endpoints(monkeypatch):
    """SenseVoice uses modelscope; single attempt, no HF endpoint loop."""
    deploy_module = load_deploy_module()
    monkeypatch.setattr(deploy_module, "_USER_HF_ENDPOINT", None)
    calls = []

    def fake_run_command(args, cwd=None, env=None):
        calls.append(env.get("HF_ENDPOINT") if env else None)

    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)

    deploy_module.download_model(
        Path("/venv/bin/python"),
        model_id="iic/SenseVoiceSmall",
        runtime="sensevoice",
    )

    assert len(calls) == 1


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


def test_ensure_environment_cuda_force_reinstalls_when_probe_fails(monkeypatch, tmp_path: Path):
    deploy_module = load_deploy_module()
    # Need unique module name? load_deploy_module always uses "asr_deploy_test" — existing pattern reuses name. OK if tests sequential.
    commands = []
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    (tmp_path / "requirements.txt").write_text("")

    def fake_run_command(args, cwd=None, env=None):
        commands.append([str(a) for a in args])

    probe_results = iter([False, True])

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)
    monkeypatch.setattr(deploy_module, "_torch_cuda_available", lambda: next(probe_results))

    deploy_module.ensure_environment(device="cuda")

    joined = [" ".join(c) for c in commands]
    assert any("uninstall" in c and "torch" in c for c in joined)
    assert any("torchaudio" in c and "uninstall" in c for c in joined)
    force_cmds = [c for c in joined if "--force-reinstall" in c]
    assert force_cmds
    assert any("torchaudio" in c for c in force_cmds)
    assert all("--index-url" in c for c in force_cmds)
    assert all("pypi.tuna" not in c for c in force_cmds)


def test_ensure_environment_cuda_skips_force_when_probe_ok(monkeypatch, tmp_path: Path):
    deploy_module = load_deploy_module()
    commands = []
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    (tmp_path / "requirements.txt").write_text("")

    def fake_run_command(args, cwd=None, env=None):
        commands.append([str(a) for a in args])

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)
    monkeypatch.setattr(deploy_module, "_torch_cuda_available", lambda: True)

    deploy_module.ensure_environment(device="cuda")

    joined = [" ".join(c) for c in commands]
    assert not any("uninstall" in c for c in joined)
    assert not any("--force-reinstall" in c for c in joined)


# ---------------------------------------------------------------------------
# Task 5: CLI --env-only / --models
# ---------------------------------------------------------------------------


def test_main_env_only_calls_ensure_environment_not_deploy(monkeypatch):
    """main(--env-only) only ensures env; does not deploy or install models."""
    deploy_module = load_deploy_module()
    ensure_calls = []
    deploy_calls = []
    install_calls = []
    download_calls = []

    monkeypatch.setattr(sys, "argv", ["deploy.py", "--env-only", "--device", "cpu"])
    monkeypatch.setattr(
        deploy_module,
        "ensure_environment",
        lambda **kwargs: ensure_calls.append(kwargs),
    )
    monkeypatch.setattr(
        deploy_module,
        "deploy",
        lambda **kwargs: deploy_calls.append(kwargs),
    )
    monkeypatch.setattr(
        deploy_module,
        "install_model",
        lambda *a, **k: install_calls.append((a, k)),
    )
    monkeypatch.setattr(
        deploy_module,
        "download_model",
        lambda *a, **k: download_calls.append((a, k)),
    )
    monkeypatch.setattr(deploy_module, "detect_best_device", lambda: "cpu")

    deploy_module.main()

    assert len(ensure_calls) == 1
    assert ensure_calls[0]["device"] == "cpu"
    assert deploy_calls == []
    assert install_calls == []
    assert download_calls == []


def test_main_models_sensevoice_small_calls_install_model(monkeypatch):
    """main(--models sensevoice-small) installs that slug via install_model."""
    deploy_module = load_deploy_module()
    install_calls = []
    deploy_calls = []
    ensure_calls = []

    monkeypatch.setattr(
        sys, "argv", ["deploy.py", "--models", "sensevoice-small", "--device", "cpu"]
    )
    monkeypatch.setattr(
        deploy_module,
        "install_model",
        lambda slug, **kwargs: install_calls.append({"slug": slug, **kwargs}),
    )
    monkeypatch.setattr(
        deploy_module,
        "deploy",
        lambda **kwargs: deploy_calls.append(kwargs),
    )
    monkeypatch.setattr(
        deploy_module,
        "ensure_environment",
        lambda **kwargs: ensure_calls.append(kwargs),
    )
    monkeypatch.setattr(deploy_module, "detect_best_device", lambda: "cpu")

    deploy_module.main()

    assert len(install_calls) == 1
    call = install_calls[0]
    assert call["slug"] == "sensevoice-small"
    assert call["model_id"] == "iic/SenseVoiceSmall"
    assert call["runtime"] == "sensevoice"
    assert call["spec"] is None
    assert call["device"] == "cpu"
    assert deploy_calls == []
    # install_model owns ensure_environment; main does not call it separately
    assert ensure_calls == []


def test_main_models_unknown_slug_raises(monkeypatch):
    """main(--models bad-slug) exits with a clear unknown-slug message."""
    deploy_module = load_deploy_module()
    install_calls = []
    deploy_calls = []

    monkeypatch.setattr(sys, "argv", ["deploy.py", "--models", "not-a-real-model"])
    monkeypatch.setattr(
        deploy_module,
        "install_model",
        lambda *a, **k: install_calls.append((a, k)),
    )
    monkeypatch.setattr(
        deploy_module,
        "deploy",
        lambda **kwargs: deploy_calls.append(kwargs),
    )
    monkeypatch.setattr(deploy_module, "detect_best_device", lambda: "cpu")

    try:
        deploy_module.main()
    except SystemExit as exc:
        msg = str(exc)
        assert "Unknown ASR model slug" in msg
        assert "not-a-real-model" in msg
    else:
        raise AssertionError("expected SystemExit for unknown slug")

    assert install_calls == []
    assert deploy_calls == []


def test_main_bare_calls_deploy(monkeypatch):
    """Bare main() (no --env-only / --models) keeps backward-compat deploy()."""
    deploy_module = load_deploy_module()
    deploy_calls = []
    ensure_calls = []
    install_calls = []

    monkeypatch.setattr(sys, "argv", ["deploy.py", "--device", "cpu"])
    monkeypatch.setattr(
        deploy_module,
        "deploy",
        lambda **kwargs: deploy_calls.append(kwargs),
    )
    monkeypatch.setattr(
        deploy_module,
        "ensure_environment",
        lambda **kwargs: ensure_calls.append(kwargs),
    )
    monkeypatch.setattr(
        deploy_module,
        "install_model",
        lambda *a, **k: install_calls.append((a, k)),
    )
    monkeypatch.setattr(deploy_module, "detect_best_device", lambda: "cpu")

    deploy_module.main()

    assert len(deploy_calls) == 1
    assert deploy_calls[0]["device"] == "cpu"
    assert ensure_calls == []
    assert install_calls == []


def test_main_env_only_prefers_over_models(monkeypatch):
    """When both --env-only and --models are passed, only ensure_environment runs."""
    deploy_module = load_deploy_module()
    ensure_calls = []
    install_calls = []
    deploy_calls = []

    monkeypatch.setattr(
        sys,
        "argv",
        ["deploy.py", "--env-only", "--models", "sensevoice-small", "--device", "cpu"],
    )
    monkeypatch.setattr(
        deploy_module,
        "ensure_environment",
        lambda **kwargs: ensure_calls.append(kwargs),
    )
    monkeypatch.setattr(
        deploy_module,
        "install_model",
        lambda *a, **k: install_calls.append((a, k)),
    )
    monkeypatch.setattr(
        deploy_module,
        "deploy",
        lambda **kwargs: deploy_calls.append(kwargs),
    )
    monkeypatch.setattr(deploy_module, "detect_best_device", lambda: "cpu")

    deploy_module.main()

    assert len(ensure_calls) == 1
    assert install_calls == []
    assert deploy_calls == []
