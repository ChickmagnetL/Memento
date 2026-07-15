from pathlib import Path

from core.embedding_model_manager import EmbeddingModelManager
from core.embedding_model_registry import get_local_embedding_model


def _complete_cache(service_dir: Path, model_id: str) -> Path:
    cache = (
        service_dir
        / "models"
        / ("models--" + model_id.replace("/", "--"))
        / "snapshots"
        / "revision"
    )
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "config.json").write_text("{}")
    (cache / "model.safetensors").write_bytes(b"x" * 1_000_001)
    return cache


def test_status_requires_config_and_weights_and_reports_devices(monkeypatch, tmp_path):
    service_dir = tmp_path / "embedding"
    service_dir.mkdir()
    incomplete = (
        service_dir
        / "models"
        / "models--BAAI--bge-m3"
        / "snapshots"
        / "revision"
    )
    incomplete.mkdir(parents=True)
    (incomplete / "model.safetensors").write_bytes(b"x" * 1_000_001)

    manager = EmbeddingModelManager(service_dir=service_dir)
    monkeypatch.setattr(manager, "_target_device", lambda: "mps")
    monkeypatch.setattr(manager, "_runtime_device", lambda: None)

    status = manager.get_status()

    assert status.environment.target_device == "mps"
    assert status.environment.runtime_device is None
    assert status.models["bge-m3"].installed is False
    assert status.models["qwen3-embedding-0.6b"].installed is False


def test_fast_status_skips_runtime_probe_and_full_status_caches_it(
    monkeypatch, tmp_path,
):
    service_dir = tmp_path / "embedding"
    python = service_dir / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()
    calls = []

    class Result:
        stdout = "mps\n"

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return Result()

    monkeypatch.setattr("core.embedding_model_manager.subprocess.run", fake_run)
    manager = EmbeddingModelManager(service_dir=service_dir)

    assert manager.get_status(probe_runtime_device=False).environment.runtime_device is None
    assert calls == []
    assert manager.get_status().environment.runtime_device == "mps"
    assert manager.get_status().environment.runtime_device == "mps"
    assert len(calls) == 1


def test_install_selected_model_ensures_environment_and_downloads_only_that_model(
    monkeypatch, tmp_path
):
    service_dir = tmp_path / "embedding"
    service_dir.mkdir()
    manager = EmbeddingModelManager(service_dir=service_dir)
    calls = []

    class FakeDeploy:
        def deploy(self, **kwargs):
            calls.append(kwargs)
            _complete_cache(service_dir, kwargs["model_id"])
            callback = kwargs["on_progress"]
            callback("model", f"Downloaded {kwargs['model_id']}", 90)

    monkeypatch.setattr(manager, "_load_deploy_module", lambda: FakeDeploy())

    manager._run_install(get_local_embedding_model("qwen3-embedding-0.6b"))

    assert len(calls) == 1
    assert calls[0]["model_id"] == "Qwen/Qwen3-Embedding-0.6B"
    assert calls[0]["device"] is None
    assert manager.get_status().models["qwen3-embedding-0.6b"].installed is True
    assert manager.get_status().models["bge-m3"].installed is False
    assert manager.get_status().progress.stage == "done"


def test_uninstall_selected_model_keeps_environment_and_other_model(monkeypatch, tmp_path):
    service_dir = tmp_path / "embedding"
    venv = service_dir / ".venv"
    venv.mkdir(parents=True)
    bge_cache = _complete_cache(service_dir, "BAAI/bge-m3")
    qwen_cache = _complete_cache(service_dir, "Qwen/Qwen3-Embedding-0.6B")
    manager = EmbeddingModelManager(service_dir=service_dir)

    class FakeDeploy:
        def uninstall_model(self, model_id):
            root = service_dir / "models" / ("models--" + model_id.replace("/", "--"))
            if root.exists():
                import shutil

                shutil.rmtree(root)

    monkeypatch.setattr(manager, "_load_deploy_module", lambda: FakeDeploy())

    manager._run_uninstall(get_local_embedding_model("bge-m3"))

    assert not bge_cache.exists()
    assert qwen_cache.exists()
    assert venv.exists()
    assert manager.get_status().progress.stage == "done"
