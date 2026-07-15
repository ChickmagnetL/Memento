"""Tests for the embedding service deployer (HF endpoint fallback)."""

import importlib.util
import subprocess
import sys
from pathlib import Path


DEPLOY_PATH = Path(__file__).resolve().parents[2] / "services" / "embedding" / "deploy.py"


def load_deploy_module(name: str = "embedding_deploy_test"):
    spec = importlib.util.spec_from_file_location(name, DEPLOY_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_hf_endpoint_candidates_default_order(monkeypatch):
    deploy_module = load_deploy_module("embedding_deploy_candidates_default")
    monkeypatch.setattr(deploy_module, "_USER_HF_ENDPOINT", None)
    assert deploy_module._hf_endpoint_candidates() == [
        "https://huggingface.co",
        "https://hf-mirror.com",
    ]


def test_hf_endpoint_candidates_known_user_prefers_then_fallback(monkeypatch):
    deploy_module = load_deploy_module("embedding_deploy_candidates_known")
    monkeypatch.setattr(deploy_module, "_USER_HF_ENDPOINT", "https://huggingface.co")
    assert deploy_module._hf_endpoint_candidates() == [
        "https://huggingface.co",
        "https://hf-mirror.com",
    ]


def test_hf_endpoint_candidates_custom_is_exclusive(monkeypatch):
    deploy_module = load_deploy_module("embedding_deploy_candidates_custom")
    monkeypatch.setattr(deploy_module, "_USER_HF_ENDPOINT", "https://hf.example.internal")
    assert deploy_module._hf_endpoint_candidates() == [
        "https://hf.example.internal",
    ]


def test_download_model_falls_back_to_second_endpoint(monkeypatch, tmp_path: Path):
    deploy_module = load_deploy_module("embedding_deploy_fallback")
    monkeypatch.setattr(deploy_module, "_USER_HF_ENDPOINT", None)
    monkeypatch.setattr(deploy_module, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(deploy_module, "VENV_DIR", tmp_path / ".venv")

    endpoints = []

    def fake_run_command(args, cwd=None, env=None):
        endpoint = env.get("HF_ENDPOINT") if env else None
        endpoints.append(endpoint)
        assert env["MEM_DOWNLOAD_MODEL_ID"] == "BAAI/bge-m3"
        assert env["MEM_DOWNLOAD_CACHE_DIR"] == str(tmp_path / "models")
        if endpoint == "https://huggingface.co":
            raise RuntimeError("could not connect to huggingface.co")
        # second endpoint succeeds — create weights so _model_present is True
        cache = (tmp_path / "models") / "models--BAAI--bge-m3" / "snapshots" / "abc"
        cache.mkdir(parents=True)
        (cache / "config.json").write_text("{}")
        (cache / "model.safetensors").write_bytes(b"x" * 1_000_001)

    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)

    deploy_module.download_model("BAAI/bge-m3")

    assert endpoints == [
        "https://huggingface.co",
        "https://hf-mirror.com",
    ]


def test_download_model_raises_when_all_endpoints_fail(monkeypatch, tmp_path: Path):
    deploy_module = load_deploy_module("embedding_deploy_all_fail")
    monkeypatch.setattr(deploy_module, "_USER_HF_ENDPOINT", None)
    monkeypatch.setattr(deploy_module, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(deploy_module, "VENV_DIR", tmp_path / ".venv")

    def fake_run_command(args, cwd=None, env=None):
        raise RuntimeError(f"down ({env.get('HF_ENDPOINT')})")

    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)

    try:
        deploy_module.download_model("BAAI/bge-m3")
    except RuntimeError as exc:
        msg = str(exc)
        assert "all HF endpoints" in msg
        assert "https://hf-mirror.com" in msg
        assert "https://huggingface.co" in msg
    else:
        raise AssertionError("expected RuntimeError when all endpoints fail")


def test_download_model_uses_mem_download_env_not_path_interpolation(monkeypatch, tmp_path: Path):
    """Windows-safe: model id / cache dir ride env vars, not the -c string."""
    deploy_module = load_deploy_module("embedding_deploy_env_pass")
    monkeypatch.setattr(deploy_module, "_USER_HF_ENDPOINT", None)
    monkeypatch.setattr(deploy_module, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(deploy_module, "VENV_DIR", tmp_path / ".venv")

    commands = []
    envs = []

    def fake_run_command(args, cwd=None, env=None):
        commands.append(args)
        envs.append(env)
        # create weights so _model_present is True after success
        cache = (tmp_path / "models") / "models--BAAI--bge-m3" / "snapshots" / "abc"
        cache.mkdir(parents=True)
        (cache / "config.json").write_text("{}")
        (cache / "model.safetensors").write_bytes(b"x" * 1_000_001)

    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)
    deploy_module.download_model("BAAI/bge-m3")

    script = " ".join(str(a) for a in commands[0])
    assert "snapshot_download" in script
    assert "SentenceTransformer" not in script
    assert "MEM_DOWNLOAD_MODEL_ID" in script
    assert "BAAI/bge-m3" not in script  # not interpolated into -c
    assert envs[0]["MEM_DOWNLOAD_MODEL_ID"] == "BAAI/bge-m3"
    assert envs[0]["MEM_DOWNLOAD_CACHE_DIR"] == str(tmp_path / "models")
    models_dir = str(tmp_path / "models")
    assert envs[0]["HF_HOME"] == models_dir
    assert envs[0]["HUGGINGFACE_HUB_CACHE"] == models_dir
    assert envs[0]["TRANSFORMERS_CACHE"] == models_dir
    assert envs[0]["HF_HUB_CACHE"] == models_dir
    assert envs[0]["PYTHONUNBUFFERED"] == "1"
    assert envs[0]["HF_HUB_DISABLE_SYMLINKS"] == "1"
    assert envs[0]["HF_HUB_ENABLE_HF_TRANSFER"] == "0"


def test_ensure_environment_cuda_force_reinstalls_when_probe_fails(monkeypatch, tmp_path: Path):
    """device=cuda + probe False after first install → uninstall + force-reinstall."""
    deploy_module = load_deploy_module("embedding_deploy_cuda_force")
    commands = []
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()

    def fake_run_command(args, cwd=None, env=None):
        commands.append([str(a) for a in args])

    probe_results = iter([False, True])  # first probe fail, after force succeed

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)
    monkeypatch.setattr(deploy_module, "_torch_cuda_available", lambda: next(probe_results))
    # requirements file may be referenced — create empty one if needed
    (tmp_path / "requirements.txt").write_text("")

    deploy_module.ensure_environment(device="cuda")

    joined = [" ".join(c) for c in commands]
    assert any("uninstall" in c and "torch" in c for c in joined)
    assert any("--force-reinstall" in c and "torch" in c for c in joined)
    force_cmds = [c for c in joined if "--force-reinstall" in c]
    assert force_cmds
    assert all("--index-url" in c for c in force_cmds)
    # no china mirror -i on force path
    assert all("pypi.tuna" not in c for c in force_cmds)


def test_ensure_environment_cuda_skips_force_when_probe_ok(monkeypatch, tmp_path: Path):
    deploy_module = load_deploy_module("embedding_deploy_cuda_ok")
    commands = []
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()

    def fake_run_command(args, cwd=None, env=None):
        commands.append([str(a) for a in args])

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)
    monkeypatch.setattr(deploy_module, "_torch_cuda_available", lambda: True)
    (tmp_path / "requirements.txt").write_text("")

    deploy_module.ensure_environment(device="cuda")

    joined = [" ".join(c) for c in commands]
    assert not any("uninstall" in c for c in joined)
    assert not any("--force-reinstall" in c for c in joined)


def test_detect_best_device_uses_mps_before_clean_venv_exists(monkeypatch):
    deploy_module = load_deploy_module("embedding_deploy_clean_macos")
    monkeypatch.setattr(deploy_module.shutil, "which", lambda name: None)
    monkeypatch.setattr(deploy_module.sys, "platform", "darwin")
    monkeypatch.setattr(
        deploy_module.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("clean macOS detection should not probe venv torch")
        ),
    )

    assert deploy_module.detect_best_device() == "mps"


def test_frozen_environment_uses_managed_toolchain(monkeypatch, tmp_path: Path):
    deploy_module = load_deploy_module("embedding_deploy_frozen_toolchain")
    calls = []
    venv = tmp_path / ".venv"
    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv)
    monkeypatch.setattr(deploy_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        deploy_module,
        "_ensure_managed_toolchain",
        lambda: (calls.append("toolchain"), venv.mkdir()),
    )
    monkeypatch.setattr(deploy_module, "run_command", lambda *args, **kwargs: None)
    (tmp_path / "requirements.txt").write_text("")

    deploy_module.ensure_environment(device="mps")

    assert calls == ["toolchain"]


def test_uninstall_model_and_all_stay_inside_managed_paths(monkeypatch, tmp_path: Path):
    deploy_module = load_deploy_module("embedding_deploy_uninstall")
    models = tmp_path / "models"
    venv = tmp_path / ".venv"
    bge = models / "models--BAAI--bge-m3"
    qwen = models / "models--Qwen--Qwen3-Embedding-0.6B"
    bge.mkdir(parents=True)
    qwen.mkdir(parents=True)
    venv.mkdir()
    keep = tmp_path / "keep.txt"
    keep.write_text("keep")
    monkeypatch.setattr(deploy_module, "MODELS_DIR", models)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv)

    deploy_module.uninstall_model("BAAI/bge-m3")

    assert not bge.exists()
    assert qwen.exists()
    assert venv.exists()

    deploy_module.uninstall_all()

    assert not models.exists()
    assert not venv.exists()
    assert keep.exists()


def test_deploy_skips_download_when_model_present(monkeypatch, tmp_path: Path):
    """deploy always ensures env; skips model download when complete weights exist."""
    deploy_module = load_deploy_module("embedding_deploy_skip_model")
    downloads = []
    commands = []
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    models_dir = tmp_path / "models"
    cache = models_dir / "models--BAAI--bge-m3"
    nested = cache / "snapshots" / "abc"
    nested.mkdir(parents=True)
    (nested / "config.json").write_text("{}")
    (nested / "model.safetensors").write_bytes(b"x" * 1_000_001)
    (tmp_path / "requirements.txt").write_text("")

    def fake_run_command(args, cwd=None, env=None):
        commands.append([str(a) for a in args])

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "MODELS_DIR", models_dir)
    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)
    monkeypatch.setattr(
        deploy_module, "download_model", lambda model_id=None: downloads.append(model_id)
    )

    deploy_module.deploy(device="cpu")

    joined = [" ".join(c) for c in commands]
    assert any("requirements.txt" in c for c in joined)
    assert any("torch" in c for c in joined)
    assert downloads == []


def test_deploy_downloads_when_model_incomplete(monkeypatch, tmp_path: Path, capsys):
    """Incomplete cache is kept for resume and triggers download."""
    deploy_module = load_deploy_module("embedding_deploy_incomplete_model")
    downloads = []
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    models_dir = tmp_path / "models"
    cache = models_dir / "models--BAAI--bge-m3"
    cache.mkdir(parents=True)
    (cache / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("")

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "MODELS_DIR", models_dir)
    monkeypatch.setattr(deploy_module, "run_command", lambda *a, **k: None)

    def fake_download(model_id=None):
        downloads.append(model_id or "default")
        # Incomplete dir should be KEPT for resume (not removed)
        assert cache.exists()
        # Create large weights so post-download verification succeeds
        nested = cache / "snapshots" / "abc"
        nested.mkdir(parents=True)
        (nested / "config.json").write_text("{}")
        (nested / "model.safetensors").write_bytes(b"x" * 1_000_001)

    monkeypatch.setattr(deploy_module, "download_model", fake_download)

    deploy_module.deploy(device="cpu", model_id="BAAI/bge-m3")

    assert downloads == ["BAAI/bge-m3"]
    out = capsys.readouterr().out
    assert "incomplete" in out
    assert "BAAI/bge-m3" in out
    assert "incomplete cache for BAAI/bge-m3, resuming download..." in out


def test_model_present_false_for_empty_or_config_only(tmp_path: Path, monkeypatch):
    deploy_module = load_deploy_module("embedding_deploy_model_present_checks")
    models_dir = tmp_path / "models"
    monkeypatch.setattr(deploy_module, "MODELS_DIR", models_dir)

    assert deploy_module._model_present("BAAI/bge-m3") is False

    cache = models_dir / "models--BAAI--bge-m3"
    cache.mkdir(parents=True)
    assert deploy_module._model_present("BAAI/bge-m3") is False

    (cache / "dummy.txt").write_text("x", encoding="utf-8")
    assert deploy_module._model_present("BAAI/bge-m3") is False

    nested = cache / "snapshots" / "abc"
    nested.mkdir(parents=True)
    (nested / "model.safetensors").write_bytes(b"weights")
    assert deploy_module._model_present("BAAI/bge-m3") is False

    (nested / "model.safetensors").write_bytes(b"x" * 1_000_001)
    assert deploy_module._model_present("BAAI/bge-m3") is False

    (nested / "config.json").write_text("{}")
    assert deploy_module._model_present("BAAI/bge-m3") is True


def test_deploy_downloads_when_model_missing(monkeypatch, tmp_path: Path):
    deploy_module = load_deploy_module("embedding_deploy_download_missing")
    downloads = []
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (tmp_path / "requirements.txt").write_text("")

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "MODELS_DIR", models_dir)
    monkeypatch.setattr(deploy_module, "run_command", lambda *a, **k: None)

    def fake_download(model_id=None):
        downloads.append(model_id or "default")
        cache = models_dir / "models--BAAI--bge-m3"
        nested = cache / "snapshots" / "abc"
        nested.mkdir(parents=True)
        (nested / "config.json").write_text("{}")
        (nested / "model.safetensors").write_bytes(b"x" * 1_000_001)

    monkeypatch.setattr(deploy_module, "download_model", fake_download)

    deploy_module.deploy(device="cpu", model_id="BAAI/bge-m3")

    assert downloads == ["BAAI/bge-m3"]


def test_deploy_raises_when_download_leaves_weights_missing(monkeypatch, tmp_path: Path):
    deploy_module = load_deploy_module("embedding_deploy_download_still_missing")
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (tmp_path / "requirements.txt").write_text("")

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "MODELS_DIR", models_dir)
    monkeypatch.setattr(deploy_module, "run_command", lambda *a, **k: None)
    monkeypatch.setattr(
        deploy_module, "download_model", lambda model_id=None: None  # no weights created
    )

    try:
        deploy_module.deploy(device="cpu", model_id="BAAI/bge-m3")
    except RuntimeError as exc:
        assert "weights still missing" in str(exc)
        assert "BAAI/bge-m3" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when weights still missing after download")


def test_deploy_force_model_wipes_and_redownloads(monkeypatch, tmp_path: Path, capsys):
    deploy_module = load_deploy_module("embedding_deploy_force_model")
    downloads = []
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    models_dir = tmp_path / "models"
    cache = models_dir / "models--BAAI--bge-m3"
    nested = cache / "snapshots" / "abc"
    nested.mkdir(parents=True)
    (nested / "config.json").write_text("{}")
    (nested / "model.safetensors").write_bytes(b"x" * 1_000_001)  # complete cache
    (tmp_path / "requirements.txt").write_text("")

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "MODELS_DIR", models_dir)
    monkeypatch.setattr(deploy_module, "run_command", lambda *a, **k: None)

    def fake_download(model_id=None):
        downloads.append(model_id or "default")
        # Cache should have been wiped before download
        assert not cache.exists()
        nested2 = cache / "snapshots" / "abc"
        nested2.mkdir(parents=True)
        (nested2 / "config.json").write_text("{}")
        (nested2 / "model.safetensors").write_bytes(b"x" * 1_000_001)

    monkeypatch.setattr(deploy_module, "download_model", fake_download)

    deploy_module.deploy(device="cpu", model_id="BAAI/bge-m3", force_model=True)

    assert downloads == ["BAAI/bge-m3"]
    out = capsys.readouterr().out
    assert "Force re-download for BAAI/bge-m3" in out


def test_main_force_model_passes_flag_to_deploy(monkeypatch):
    deploy_module = load_deploy_module("embedding_deploy_main_force_model")
    deploy_calls = []

    monkeypatch.setattr(sys, "argv", ["deploy.py", "--force-model", "--device", "cpu"])
    monkeypatch.setattr(
        deploy_module,
        "deploy",
        lambda **kwargs: deploy_calls.append(kwargs),
    )
    monkeypatch.setattr(deploy_module, "detect_best_device", lambda: "cpu")

    deploy_module.main()

    assert len(deploy_calls) == 1
    assert deploy_calls[0]["force_model"] is True
    assert deploy_calls[0]["device"] == "cpu"


# ---------------------------------------------------------------------------
# Task 5: env_only / CLI --env-only
# ---------------------------------------------------------------------------


def test_deploy_env_only_skips_download_even_when_missing(monkeypatch, tmp_path: Path):
    """deploy(env_only=True) ensures env but never calls download_model."""
    deploy_module = load_deploy_module("embedding_deploy_env_only")
    downloads = []
    ensure_calls = []
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (tmp_path / "requirements.txt").write_text("")

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "MODELS_DIR", models_dir)
    monkeypatch.setattr(
        deploy_module,
        "ensure_environment",
        lambda **kwargs: ensure_calls.append(kwargs),
    )
    monkeypatch.setattr(
        deploy_module, "download_model", lambda model_id=None: downloads.append(model_id)
    )

    deploy_module.deploy(device="cpu", model_id="BAAI/bge-m3", env_only=True)

    assert len(ensure_calls) == 1
    assert ensure_calls[0]["device"] == "cpu"
    assert downloads == []


def test_main_env_only_passes_flag_to_deploy(monkeypatch):
    """main(--env-only) forwards env_only=True into deploy()."""
    deploy_module = load_deploy_module("embedding_deploy_main_env_only")
    deploy_calls = []

    monkeypatch.setattr(sys, "argv", ["deploy.py", "--env-only", "--device", "cpu"])
    monkeypatch.setattr(
        deploy_module,
        "deploy",
        lambda **kwargs: deploy_calls.append(kwargs),
    )
    monkeypatch.setattr(deploy_module, "detect_best_device", lambda: "cpu")

    deploy_module.main()

    assert len(deploy_calls) == 1
    assert deploy_calls[0]["env_only"] is True
    assert deploy_calls[0]["device"] == "cpu"
    assert deploy_calls[0]["model_id"] == "BAAI/bge-m3"


def test_download_model_exit_130_raises_system_exit(monkeypatch, tmp_path: Path):
    deploy_module = load_deploy_module("embedding_deploy_exit_130")
    monkeypatch.setattr(deploy_module, "_USER_HF_ENDPOINT", None)
    monkeypatch.setattr(deploy_module, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(deploy_module, "VENV_DIR", tmp_path / ".venv")

    def fake_run_command(args, cwd=None, env=None):
        raise subprocess.CalledProcessError(130, cmd=args)

    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)

    try:
        deploy_module.download_model("BAAI/bge-m3")
    except SystemExit as exc:
        assert exc.code == 130
    else:
        raise AssertionError("expected SystemExit(130)")


def test_download_model_falls_back_when_weights_missing_after_success(monkeypatch, tmp_path: Path):
    """run_command succeeds but no weights → treat as fail, try next endpoint."""
    deploy_module = load_deploy_module("embedding_deploy_weights_missing_fallback")
    monkeypatch.setattr(deploy_module, "_USER_HF_ENDPOINT", None)
    monkeypatch.setattr(deploy_module, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(deploy_module, "VENV_DIR", tmp_path / ".venv")

    endpoints = []

    def fake_run_command(args, cwd=None, env=None):
        endpoint = env.get("HF_ENDPOINT") if env else None
        endpoints.append(endpoint)
        if endpoint == "https://hf-mirror.com":
            # second endpoint creates weights
            cache = (tmp_path / "models") / "models--BAAI--bge-m3" / "snapshots" / "abc"
            cache.mkdir(parents=True)
            (cache / "config.json").write_text("{}")
            (cache / "model.safetensors").write_bytes(b"x" * 1_000_001)
        # first endpoint: succeed but no weights

    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)
    deploy_module.download_model("BAAI/bge-m3")
    assert endpoints == [
        "https://huggingface.co",
        "https://hf-mirror.com",
    ]


def test_cache_has_model_weights_index_alone_is_false(tmp_path: Path, monkeypatch):
    """Index-only cache must not count as complete (align with server)."""
    deploy_module = load_deploy_module("embedding_deploy_index_alone")
    models_dir = tmp_path / "models"
    monkeypatch.setattr(deploy_module, "MODELS_DIR", models_dir)
    nested = models_dir / "models--BAAI--bge-m3" / "snapshots" / "abc"
    nested.mkdir(parents=True)
    (nested / "model.safetensors.index.json").write_text("{}", encoding="utf-8")
    assert deploy_module._cache_has_model_weights(nested) is False
    assert deploy_module._model_present("BAAI/bge-m3") is False


def test_cuda_torch_index_default_is_cu124():
    """cu121 caps at torch 2.5.1 which blocks torch.load (CVE-2025-32434 needs >=2.6)."""
    deploy_module = load_deploy_module("embedding_deploy_cu124_default")
    assert deploy_module.CUDA_TORCH_INDEX_URL == "https://download.pytorch.org/whl/cu124"


def test_ensure_environment_cuda_installs_from_cu124_index(monkeypatch, tmp_path: Path):
    """device=cuda initial torch install must target the cu124 index (not cu121)."""
    deploy_module = load_deploy_module("embedding_deploy_cuda_install_cu124")
    commands = []
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()

    def fake_run_command(args, cwd=None, env=None):
        commands.append([str(a) for a in args])

    monkeypatch.setattr(deploy_module, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(deploy_module, "VENV_DIR", venv_dir)
    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)
    monkeypatch.setattr(deploy_module, "_torch_cuda_available", lambda: True)
    (tmp_path / "requirements.txt").write_text("")

    deploy_module.ensure_environment(device="cuda")

    # The initial (non-force) torch install command.
    torch_cmds = [
        c for c in commands
        if "install" in c and "torch" in c and "--force-reinstall" not in c
    ]
    assert torch_cmds, "expected a torch install command"
    cmd = torch_cmds[0]
    assert "--index-url" in cmd
    idx = cmd.index("--index-url")
    assert cmd[idx + 1] == "https://download.pytorch.org/whl/cu124"
    assert "cu121" not in " ".join(cmd)


def test_download_model_sets_hf_hub_disable_xet(monkeypatch, tmp_path: Path):
    """Download subprocess env must force HF_HUB_DISABLE_XET=1 (xet native stalls)."""
    deploy_module = load_deploy_module("embedding_deploy_disable_xet")
    monkeypatch.setattr(deploy_module, "_USER_HF_ENDPOINT", None)
    monkeypatch.setattr(deploy_module, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(deploy_module, "VENV_DIR", tmp_path / ".venv")

    envs = []

    def fake_run_command(args, cwd=None, env=None):
        envs.append(env)
        cache = (tmp_path / "models") / "models--BAAI--bge-m3" / "snapshots" / "abc"
        cache.mkdir(parents=True)
        (cache / "config.json").write_text("{}")
        (cache / "model.safetensors").write_bytes(b"x" * 1_000_001)

    monkeypatch.setattr(deploy_module, "run_command", fake_run_command)
    deploy_module.download_model("BAAI/bge-m3")

    assert envs[0]["HF_HUB_DISABLE_XET"] == "1"
