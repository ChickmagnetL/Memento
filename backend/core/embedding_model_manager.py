"""Local Embedding model status, install, and uninstall orchestration."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from core.embedding_model_registry import (
    EmbeddingModel,
    get_local_embedding_model,
    list_local_embedding_models,
)
from schemas.embedding import (
    EmbeddingEnvironmentStatus,
    EmbeddingManagerProgress,
    EmbeddingManagerStatus,
    EmbeddingModelStatus,
)


_CONFIG_NAMES = ("config.json", "modules.json", "config_sentence_transformers.json")


class EmbeddingModelManager:
    def __init__(self, service_dir: Path) -> None:
        self.service_dir = Path(service_dir)
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._job_future: Future | None = None
        self._job_lock = threading.RLock()
        self._progress_state = EmbeddingManagerProgress()

    def _service_python(self) -> Path:
        if sys.platform == "win32":
            return self.service_dir / ".venv" / "Scripts" / "python.exe"
        return self.service_dir / ".venv" / "bin" / "python"

    def _runtime_device(self) -> str | None:
        python = self._service_python()
        if not python.is_file():
            return None
        script = (
            "import torch;"
            " print('cuda' if torch.cuda.is_available()"
            " else 'mps' if torch.backends.mps.is_available() else 'cpu')"
        )
        try:
            result = subprocess.run(
                [str(python), "-c", script],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception:
            return None
        device = result.stdout.strip()
        return device if device in {"cuda", "mps", "cpu"} else None

    def _target_device(self) -> str:
        if shutil.which("nvidia-smi") is not None:
            return "cuda"
        if sys.platform == "darwin":
            return "mps"
        return self._runtime_device() or "cpu"

    def _cache_roots(self, model: EmbeddingModel) -> list[Path]:
        slug = model.model_id.replace("/", "--")
        models_dir = self.service_dir / "models"
        return [
            models_dir / f"models--{slug}",
            models_dir / f"models--sentence-transformers--{slug}",
        ]

    @staticmethod
    def _has_large_weights(path: Path) -> bool:
        if not path.is_dir():
            return False
        for pattern in ("model.safetensors", "pytorch_model.bin", "*.safetensors"):
            for candidate in path.rglob(pattern):
                try:
                    if candidate.is_file() and candidate.stat().st_size > 1_000_000:
                        return True
                except OSError:
                    continue
        return False

    @classmethod
    def _is_complete_model(cls, path: Path) -> bool:
        return any((path / name).is_file() for name in _CONFIG_NAMES) and cls._has_large_weights(path)

    def _find_cache(self, model: EmbeddingModel) -> Path | None:
        for root in self._cache_roots(model):
            snapshots = root / "snapshots"
            if snapshots.is_dir():
                try:
                    candidates = [path for path in snapshots.iterdir() if path.is_dir()]
                except OSError:
                    candidates = []
                for candidate in candidates:
                    if self._is_complete_model(candidate):
                        return candidate
            if self._is_complete_model(root):
                return root
        return None

    def _set_progress(
        self,
        stage: str,
        detail: str = "",
        *,
        model_slug: str | None = None,
        percent: int | None = None,
        error: str | None = None,
    ) -> None:
        with self._job_lock:
            self._progress_state = EmbeddingManagerProgress(
                stage=stage,
                model_slug=model_slug,
                percent=percent,
                detail=detail,
                error=error,
                done=stage in {"done", "failed"},
            )

    def _progress(self) -> EmbeddingManagerProgress:
        with self._job_lock:
            if self._job_future is not None and self._job_future.done():
                try:
                    self._job_future.result()
                except Exception:
                    pass
                self._job_future = None
            return self._progress_state

    def _load_deploy_module(self):
        path = self.service_dir / "deploy.py"
        spec = importlib.util.spec_from_file_location("memento_embedding_deploy_manager", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Embedding deploy.py not found")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def get_status(self) -> EmbeddingManagerStatus:
        python = self._service_python()
        progress = self._progress()
        models: dict[str, EmbeddingModelStatus] = {}
        for model in list_local_embedding_models():
            cache = self._find_cache(model)
            installing = (
                progress.model_slug == model.slug
                and progress.stage not in {"idle", "done", "failed"}
            )
            models[model.slug] = EmbeddingModelStatus(
                slug=model.slug,
                label=model.label,
                model_id=model.model_id,
                installed=cache is not None,
                installing=installing,
                cache_path=str(cache) if cache else None,
                last_error=progress.error if progress.model_slug == model.slug else None,
            )
        return EmbeddingManagerStatus(
            environment=EmbeddingEnvironmentStatus(
                venv_exists=(self.service_dir / ".venv").is_dir(),
                service_python_exists=python.is_file(),
                service_dir_exists=self.service_dir.is_dir(),
                platform=sys.platform,
                target_device=self._target_device(),
                runtime_device=self._runtime_device(),
            ),
            models=models,
            progress=progress,
        )

    def install_model(self, slug: str) -> EmbeddingManagerProgress:
        model = get_local_embedding_model(slug)
        with self._job_lock:
            if self._job_future is not None and not self._job_future.done():
                return self._progress_state
            self._set_progress("queued", f"Install {slug} queued", model_slug=slug, percent=0)
            self._job_future = self._executor.submit(self._run_install, model)
            return self._progress_state

    def _run_install(self, model: EmbeddingModel) -> None:
        try:
            deploy_module = self._load_deploy_module()

            def on_progress(stage: str, detail: str, percent: int | None = None) -> None:
                reported_stage = "verifying" if stage == "done" else stage
                self._set_progress(
                    reported_stage,
                    detail,
                    model_slug=model.slug,
                    percent=percent,
                )

            deploy_module.deploy(
                device=None,
                model_id=model.model_id,
                on_progress=on_progress,
            )
            if self._find_cache(model) is None:
                raise RuntimeError(f"Installed model {model.model_id} is not loadable")
            self._set_progress(
                "done",
                f"Model {model.slug} installed",
                model_slug=model.slug,
                percent=100,
            )
        except Exception as exc:
            self._set_progress(
                "failed",
                f"Install failed: {exc}",
                model_slug=model.slug,
                error=str(exc),
            )

    def uninstall_model(self, slug: str) -> EmbeddingManagerProgress:
        model = get_local_embedding_model(slug)
        with self._job_lock:
            if self._job_future is not None and not self._job_future.done():
                return self._progress_state
            self._set_progress("queued", f"Uninstall {slug} queued", model_slug=slug, percent=0)
            self._job_future = self._executor.submit(self._run_uninstall, model)
            return self._progress_state

    def _run_uninstall(self, model: EmbeddingModel) -> None:
        try:
            from core.rag import embedding_supervisor

            embedding_supervisor.shutdown()
            self._set_progress(
                "uninstalling",
                f"Removing {model.slug}",
                model_slug=model.slug,
                percent=30,
            )
            self._load_deploy_module().uninstall_model(model.model_id)
            self._set_progress(
                "done",
                f"Model {model.slug} uninstalled",
                model_slug=model.slug,
                percent=100,
            )
        except Exception as exc:
            self._set_progress(
                "failed",
                f"Uninstall failed: {exc}",
                model_slug=model.slug,
                error=str(exc),
            )

    def uninstall_all(self) -> EmbeddingManagerProgress:
        with self._job_lock:
            if self._job_future is not None and not self._job_future.done():
                return self._progress_state
            self._set_progress("queued", "Uninstall all queued", percent=0)
            self._job_future = self._executor.submit(self._run_uninstall_all)
            return self._progress_state

    def _run_uninstall_all(self) -> None:
        try:
            from core.rag import embedding_supervisor

            embedding_supervisor.shutdown()
            self._set_progress("uninstalling", "Removing local Embedding environment", percent=30)
            self._load_deploy_module().uninstall_all()
            self._set_progress("done", "Local Embedding environment removed", percent=100)
        except Exception as exc:
            self._set_progress("failed", f"Uninstall all failed: {exc}", error=str(exc))
