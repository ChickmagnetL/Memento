"""Local Embedding model registry used by Settings model management."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingModel:
    slug: str
    label: str
    model_id: str


_MODELS = [
    EmbeddingModel("bge-m3", "BGE-M3", "BAAI/bge-m3"),
    EmbeddingModel(
        "qwen3-embedding-0.6b",
        "Qwen3 Embedding 0.6B",
        "Qwen/Qwen3-Embedding-0.6B",
    ),
]

_BY_SLUG = {model.slug: model for model in _MODELS}


def list_local_embedding_models() -> list[EmbeddingModel]:
    return list(_MODELS)


def get_local_embedding_model(slug: str) -> EmbeddingModel:
    return _BY_SLUG[slug]
