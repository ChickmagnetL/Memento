from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

# Relative import fails under file-based test loader; fall back to sys.modules name used by tests
try:
    from .paths import ASR_DIR, EMBEDDING_DIR
except ImportError:
    from node_app_paths import ASR_DIR, EMBEDDING_DIR


@dataclass(frozen=True)
class AsrModelSpec:
    slug: str
    label: str
    model_id: str
    runtime: str  # sensevoice | moonshine
    spec: str | None  # moonshine arch spec
    size: str


@dataclass(frozen=True)
class EmbeddingModelSpec:
    slug: str
    label: str
    model_id: str


ASR_MODELS: list[AsrModelSpec] = [
    AsrModelSpec("sensevoice-small", "SenseVoice Small", "iic/SenseVoiceSmall", "sensevoice", None, "0.9GB"),
    AsrModelSpec("moonshine-tiny-en", "Moonshine Tiny EN", "moonshine_voice/tiny-en", "moonshine", "tiny-en", "71MB"),
    AsrModelSpec("moonshine-base-en", "Moonshine Base EN", "moonshine_voice/base-en", "moonshine", "base-en", "238MB"),
    AsrModelSpec("moonshine-tiny-streaming-en", "Moonshine Tiny Streaming EN", "moonshine_voice/tiny-streaming-en", "moonshine", "tiny-streaming-en", "80MB"),
    AsrModelSpec("moonshine-small-streaming-en", "Moonshine Small Streaming EN", "moonshine_voice/small-streaming-en", "moonshine", "small-streaming-en", "235MB"),
    AsrModelSpec("moonshine-medium-streaming-en", "Moonshine Medium Streaming EN", "moonshine_voice/medium-streaming-en", "moonshine", "medium-streaming-en", "429MB"),
]

EMBEDDING_MODELS: list[EmbeddingModelSpec] = [
    EmbeddingModelSpec("bge-m3", "BGE-M3", "BAAI/bge-m3"),
    EmbeddingModelSpec("qwen3-embedding-0.6b", "Qwen3 Embedding 0.6B", "Qwen/Qwen3-Embedding-0.6B"),
]


def _sensevoice_installed(asr_dir: Path) -> bool:
    root = asr_dir / "models" / "sensevoice"
    if not root.is_dir():
        return False
    if (root / "iic" / "SenseVoiceSmall" / "model.pt").is_file():
        return True
    return any(root.rglob("model.pt"))


def _moonshine_installed(asr_dir: Path, spec: str) -> bool:
    return (asr_dir / "models" / "moonshine" / "download.moonshine.ai" / "model" / spec / "quantized").is_dir()


def check_asr_models(asr_dir: Path | None = None) -> dict[str, bool]:
    base = asr_dir or ASR_DIR
    out: dict[str, bool] = {}
    for m in ASR_MODELS:
        if m.runtime == "sensevoice":
            out[m.slug] = _sensevoice_installed(base)
        else:
            out[m.slug] = _moonshine_installed(base, m.spec or "")
    return out


def embedding_cache_dir(emb_dir: Path, model_id: str) -> Path:
    """Return MODELS_DIR / models--{org}--{name}."""
    return emb_dir / "models" / ("models--" + model_id.replace("/", "--"))


def _cache_has_model_weights(cache_dir: Path) -> bool:
    """True if cache_dir contains complete model weight files (not just config/tokenizer).

    Named weights and shards must be >1MB. Index alone does NOT count.
    """
    if not cache_dir.is_dir():
        return False
    for name in ("model.safetensors", "pytorch_model.bin"):
        for p in cache_dir.rglob(name):
            try:
                if p.is_file() and p.stat().st_size > 1_000_000:
                    return True
            except OSError:
                continue
    for p in cache_dir.rglob("*.safetensors"):
        try:
            if p.is_file() and p.stat().st_size > 1_000_000:
                return True
        except OSError:
            continue
    return False


def _embedding_cache_dirs(emb_dir: Path, model_id: str) -> list[Path]:
    """Return candidate HF cache dirs under emb_dir/models for *model_id*."""
    slug = model_id.replace("/", "--")
    models_root = emb_dir / "models"
    return [
        models_root / f"models--{slug}",
        models_root / f"models--sentence-transformers--{slug}",
    ]


def check_embedding_models(emb_dir: Path | None = None) -> dict[str, bool]:
    base = emb_dir or EMBEDDING_DIR
    return {
        m.slug: any(_cache_has_model_weights(p) for p in _embedding_cache_dirs(base, m.model_id))
        for m in EMBEDDING_MODELS
    }


def asr_by_slug(slug: str) -> AsrModelSpec:
    for m in ASR_MODELS:
        if m.slug == slug:
            return m
    raise KeyError(slug)


def embedding_by_slug(slug: str) -> EmbeddingModelSpec:
    for m in EMBEDDING_MODELS:
        if m.slug == slug:
            return m
    raise KeyError(slug)


def asr_cache_paths(asr_dir: Path, slug: str) -> list[Path]:
    """Return cache path(s) to delete for an ASR model slug."""
    m = asr_by_slug(slug)
    if m.runtime == "sensevoice":
        return [asr_dir / "models" / "sensevoice"]
    # Prefer model-specific moonshine path, not the entire moonshine root
    return [
        asr_dir / "models" / "moonshine" / "download.moonshine.ai" / "model" / (m.spec or ""),
    ]


def uninstall_asr_model(slug: str, asr_dir: Path | None = None) -> bool:
    """Delete cache dirs for slug. Return True if something was removed. Never touch .venv."""
    base = asr_dir or ASR_DIR
    removed = False
    for path in asr_cache_paths(base, slug):
        if path.exists():
            shutil.rmtree(path)
            removed = True
    return removed


def uninstall_embedding_model(slug: str, emb_dir: Path | None = None) -> bool:
    """Delete all candidate HF cache dirs for slug. Return True if any removed. Never touch .venv."""
    base = emb_dir or EMBEDDING_DIR
    m = embedding_by_slug(slug)
    removed = False
    for cache in _embedding_cache_dirs(base, m.model_id):
        if cache.exists():
            shutil.rmtree(cache)
            removed = True
    return removed
