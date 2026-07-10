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
# Harmless elsewhere; set HF_ENDPOINT to override.
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

SERVICE_DIR = Path(__file__).resolve().parent
MODELS_DIR = SERVICE_DIR / "models"

app = FastAPI(title="Memento Embedding Service", version="0.1.0")

# --- Lazy model cache ---
_embedding_model: Optional[object] = None
_loaded_model_id: Optional[str] = None

DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
AVAILABLE_MODELS = [DEFAULT_EMBEDDING_MODEL]

AVAILABLE_MODELS_HF = {"all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2"}


def _hf_cache_dirname(model_id: str) -> str:
    repo = AVAILABLE_MODELS_HF.get(model_id, model_id)
    return "models--" + repo.replace("/", "--")


def _embedding_installed(model_id: str) -> bool:
    return (MODELS_DIR / _hf_cache_dirname(model_id)).is_dir()


def _get_device() -> str:
    """Resolve the torch device from EMBEDDING_DEVICE env var or auto-detect."""
    device = os.environ.get("EMBEDDING_DEVICE", "").strip()
    if device:
        return device
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def _load_model(model_id: str) -> object:
    """Load and cache the sentence-transformers model."""
    global _embedding_model, _loaded_model_id
    if _embedding_model is not None and _loaded_model_id == model_id:
        return _embedding_model

    from sentence_transformers import SentenceTransformer
    device = _get_device()
    _embedding_model = SentenceTransformer(model_id, device=device, cache_folder=str(MODELS_DIR))
    _loaded_model_id = model_id
    return _embedding_model


# --- Pydantic models ---

class EmbeddingRequest(BaseModel):
    model: str = DEFAULT_EMBEDDING_MODEL
    input: list[str]


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
        vectors = model.encode(request.input, normalize_embeddings=True)
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