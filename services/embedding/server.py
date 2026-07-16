"""Memento Embedding Service — standalone OpenAI-compatible embedding server.

Runs in its own venv because sentence-transformers/torch are heavy.
Start with: bash run.sh
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Default to the China HuggingFace mirror (model downloads go via HF).
# Harmless elsewhere; set HF_ENDPOINT before start to override
# (e.g. HF_ENDPOINT=https://huggingface.co).
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

SERVICE_DIR = Path(__file__).resolve().parent
MODELS_DIR = SERVICE_DIR / "models"

app = FastAPI(title="Memento Embedding Service", version="0.1.1")

# --- Lazy model cache ---
_embedding_model: Optional[object] = None
_loaded_model_id: Optional[str] = None

AVAILABLE_MODELS = ["BAAI/bge-m3", "Qwen/Qwen3-Embedding-0.6B"]
AVAILABLE_MODELS_HF = {
    "BAAI/bge-m3": "BAAI/bge-m3",
    "Qwen/Qwen3-Embedding-0.6B": "Qwen/Qwen3-Embedding-0.6B",
}
# Static API default for request body; warmup/list prefer first installed.
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"

_CONFIG_NAMES = ("config.json", "modules.json", "config_sentence_transformers.json")
_LARGE_BLOB_BYTES = 50_000_000


def default_embedding_model() -> str:
    """Return first installed catalog model, else preferred BAAI/bge-m3."""
    for model_id in AVAILABLE_MODELS:
        if _embedding_installed(model_id):
            return model_id
    return DEFAULT_EMBEDDING_MODEL


def _hf_cache_dirname(model_id: str) -> str:
    repo = AVAILABLE_MODELS_HF.get(model_id, model_id)
    return "models--" + repo.replace("/", "--")


def _path_is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _model_search_roots() -> list[Path]:
    """Return model search roots: MODELS_DIR plus HF_HOME only if under SERVICE_DIR."""
    roots = [MODELS_DIR]
    hf_home = os.environ.get("HF_HOME", "").strip()
    if not hf_home:
        return roots
    try:
        p = Path(hf_home).expanduser().resolve()
        service = SERVICE_DIR.resolve()
        if p.is_dir() and _path_is_under(p, service):
            if p not in {r.resolve() for r in roots}:
                roots.append(p)
    except Exception:
        pass
    return roots


def _dir_has_model_config(path: Path) -> bool:
    return any((path / name).is_file() for name in _CONFIG_NAMES)


def _cache_has_model_weights(cache_dir: Path) -> bool:
    """True if cache_dir contains complete model weight files (not just config/tokenizer)."""
    if not cache_dir.is_dir():
        return False
    # Single-file weights must be large enough to be more than a stub/partial file.
    for name in ("model.safetensors", "pytorch_model.bin"):
        for p in cache_dir.rglob(name):
            try:
                if p.is_file() and p.stat().st_size > 1_000_000:
                    return True
            except OSError:
                continue
    # Sharded or alternate names: any large safetensors shard is enough.
    # Index alone is NOT enough (matches installed tests).
    for p in cache_dir.rglob("*.safetensors"):
        try:
            if p.is_file() and p.stat().st_size > 1_000_000:
                return True
        except OSError:
            continue
    return False


def _dir_is_complete_model(path: Path) -> bool:
    """True when directory has both model config and large weight files."""
    return _dir_has_model_config(path) and _cache_has_model_weights(path)


def _blobs_only_incomplete(root: Path) -> bool:
    """True if snapshots have no complete model but blobs has a large file."""
    snapshots = root / "snapshots"
    if snapshots.is_dir():
        try:
            for snap in snapshots.iterdir():
                if snap.is_dir() and _dir_is_complete_model(snap):
                    return False
        except OSError:
            pass
    blobs = root / "blobs"
    if not blobs.is_dir():
        return False
    try:
        for p in blobs.iterdir():
            try:
                if p.is_file() and p.stat().st_size > _LARGE_BLOB_BYTES:
                    return True
            except OSError:
                continue
    except OSError:
        return False
    return False


def _find_local_model_path(model_id: str) -> Optional[Path]:
    """Resolve a filesystem path to local model weights, or None if incomplete/missing.

    Prefers HF hub snapshot dirs under search roots so SentenceTransformer can load
    by path (needed on Windows where hub-id + cache_folder resolution fails).
    Requires both config and large weight files. Blobs-only cache is incomplete.
    """
    repo = AVAILABLE_MODELS_HF.get(model_id, model_id)
    slug = repo.replace("/", "--")
    for models_root in _model_search_roots():
        candidates = [
            models_root / f"models--{slug}",
            models_root / f"models--sentence-transformers--{slug}",
        ]
        for root in candidates:
            if not root.is_dir():
                continue
            if _blobs_only_incomplete(root):
                continue
            snapshots = root / "snapshots"
            if snapshots.is_dir():
                try:
                    snap_dirs = [p for p in snapshots.iterdir() if p.is_dir()]
                except OSError:
                    snap_dirs = []
                # Prefer newest snapshot by mtime when multiple exist.
                snap_dirs.sort(
                    key=lambda p: p.stat().st_mtime if p.exists() else 0,
                    reverse=True,
                )
                for snap in snap_dirs:
                    if _dir_is_complete_model(snap):
                        return snap
            if _dir_is_complete_model(root):
                return root
    return None


def _embedding_installed(model_id: str) -> bool:
    return _find_local_model_path(model_id) is not None


def _is_qwen_embedding_model(model_id: str) -> bool:
    return model_id.startswith("Qwen/") or "Qwen3-Embedding" in model_id


def _get_device() -> str:
    """Resolve the torch device from EMBEDDING_DEVICE env var or auto-detect."""
    device = os.environ.get("EMBEDDING_DEVICE", "").strip()
    if device:
        # Verify requested accelerator is actually usable with installed torch.
        if device == "cuda":
            try:
                import torch
                if torch.cuda.is_available():
                    return "cuda"
            except ImportError:
                pass
            print(
                "WARNING: EMBEDDING_DEVICE=cuda but torch.cuda.is_available() is False; "
                "falling back to cpu. Reinstall CUDA torch in the embedding venv."
            )
            return "cpu"
        if device == "mps":
            try:
                import torch
                if torch.backends.mps.is_available():
                    return "mps"
            except Exception:
                pass
            print(
                "WARNING: EMBEDDING_DEVICE=mps but torch MPS is unavailable; "
                "falling back to cpu."
            )
            return "cpu"
        return device  # cpu or other explicit values pass through
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def _is_cuda_oom(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "out of memory" in msg or ("cuda" in msg and "memory" in msg)


def _load_model(model_id: str) -> object:
    """Load and cache the sentence-transformers model."""
    global _embedding_model, _loaded_model_id
    if _embedding_model is not None and _loaded_model_id == model_id:
        return _embedding_model

    from sentence_transformers import SentenceTransformer
    device = _get_device()
    local_path = _find_local_model_path(model_id)

    def _try_load(dev: str, *, model_name: str, local_only: bool, use_cache_folder: bool):
        kwargs = {"device": dev, "local_files_only": local_only}
        if use_cache_folder:
            kwargs["cache_folder"] = str(MODELS_DIR)
        return SentenceTransformer(model_name, **kwargs)

    last_exc: Optional[Exception] = None
    if local_path is not None:
        try:
            _embedding_model = _try_load(
                device, model_name=str(local_path), local_only=True, use_cache_folder=False
            )
            _loaded_model_id = model_id
            return _embedding_model
        except Exception as exc:
            last_exc = exc
            if device != "cpu" and _is_cuda_oom(exc):
                print(f"WARNING: Embedding load OOM on {device}; retrying on cpu...")
                try:
                    _embedding_model = _try_load(
                        "cpu", model_name=str(local_path), local_only=True, use_cache_folder=False
                    )
                    _loaded_model_id = model_id
                    return _embedding_model
                except Exception as exc2:
                    last_exc = exc2
            print(
                f"WARNING: local path load failed for {model_id} path={local_path}: {exc}; "
                "retrying with network allowed"
            )

    # hub fallback
    try:
        _embedding_model = _try_load(
            device, model_name=model_id, local_only=False, use_cache_folder=True
        )
        _loaded_model_id = model_id
        return _embedding_model
    except Exception as exc:
        last_exc = exc
        if device != "cpu" and _is_cuda_oom(exc):
            print(f"WARNING: Embedding load OOM on {device}; retrying on cpu...")
            try:
                _embedding_model = _try_load(
                    "cpu", model_name=model_id, local_only=False, use_cache_folder=True
                )
                _loaded_model_id = model_id
                return _embedding_model
            except Exception as exc2:
                last_exc = exc2
        if local_path is not None:
            if _dir_is_complete_model(local_path):
                raise RuntimeError(
                    f"Failed to load embedding model '{model_id}' from {local_path}: "
                    f"{type(last_exc).__name__}: {last_exc}"
                ) from last_exc
            raise RuntimeError(
                f"Failed to load embedding model '{model_id}' "
                f"(cache incomplete, re-deploy model; local_path={local_path}): {last_exc}"
            ) from last_exc
        raise


# --- Pydantic models ---

class EmbeddingRequest(BaseModel):
    model: str = DEFAULT_EMBEDDING_MODEL
    input: list[str]
    input_type: Optional[str] = None  # "query" | "document" | None


class EmbeddingItem(BaseModel):
    index: int
    embedding: list[float]


class EmbeddingResponse(BaseModel):
    data: list[EmbeddingItem]
    model: str
    usage: dict = {"prompt_tokens": 0, "total_tokens": 0}


class ModelItem(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "memento"


class ModelListResponse(BaseModel):
    data: list[ModelItem]


# --- Endpoints ---

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models() -> ModelListResponse:
    return ModelListResponse(
        data=[ModelItem(id=m) for m in AVAILABLE_MODELS if _embedding_installed(m)]
    )


@app.post("/v1/warmup")
async def warmup() -> dict:
    model_id = default_embedding_model()
    if not _embedding_installed(model_id):
        raise HTTPException(
            status_code=503,
            detail=f"Embedding model not installed: {model_id}",
        )
    try:
        _load_model(model_id)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load embedding model '{model_id}': {exc}",
        )
    return {"status": "ok", "model": model_id}


@app.post("/v1/embeddings")
async def create_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
    try:
        model = _load_model(request.model)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load embedding model '{request.model}': {exc}",
        )

    try:
        encode_kwargs: dict = {"normalize_embeddings": True}
        if _is_qwen_embedding_model(request.model) and request.input_type == "query":
            encode_kwargs["prompt_name"] = "query"
        vectors = model.encode(request.input, **encode_kwargs)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Embedding inference failed: {exc}",
        )

    data = [
        EmbeddingItem(index=i, embedding=vec.tolist())
        for i, vec in enumerate(vectors)
    ]
    return EmbeddingResponse(data=data, model=request.model)
