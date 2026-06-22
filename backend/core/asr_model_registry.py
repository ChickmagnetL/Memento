"""Local ASR model registry — stable slugs for UI/API, model ids for download."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AsrModel:
    """A local ASR model known to the system."""

    slug: str
    family: str
    label: str
    model_id: str
    spec: Optional[str]
    size: str
    runtime: str  # "sensevoice" or "moonshine"


_MODELS: list[AsrModel] = [
    AsrModel(
        slug="sensevoice-small",
        family="sensevoice",
        label="SenseVoice Small",
        model_id="iic/SenseVoiceSmall",
        spec=None,
        size="0.9GB",
        runtime="sensevoice",
    ),
    AsrModel(
        slug="moonshine-tiny-en",
        family="moonshine",
        label="Moonshine Tiny EN",
        model_id="moonshine_voice/tiny-en",
        spec="tiny-en",
        size="71MB",
        runtime="moonshine",
    ),
    AsrModel(
        slug="moonshine-base-en",
        family="moonshine",
        label="Moonshine Base EN",
        model_id="moonshine_voice/base-en",
        spec="base-en",
        size="238MB",
        runtime="moonshine",
    ),
    AsrModel(
        slug="moonshine-tiny-streaming-en",
        family="moonshine",
        label="Moonshine Tiny Streaming EN",
        model_id="moonshine_voice/tiny-streaming-en",
        spec="tiny-streaming-en",
        size="80MB",
        runtime="moonshine",
    ),
    AsrModel(
        slug="moonshine-small-streaming-en",
        family="moonshine",
        label="Moonshine Small Streaming EN",
        model_id="moonshine_voice/small-streaming-en",
        spec="small-streaming-en",
        size="235MB",
        runtime="moonshine",
    ),
    AsrModel(
        slug="moonshine-medium-streaming-en",
        family="moonshine",
        label="Moonshine Medium Streaming EN",
        model_id="moonshine_voice/medium-streaming-en",
        spec="medium-streaming-en",
        size="429MB",
        runtime="moonshine",
    ),
]

_BY_SLUG: dict[str, AsrModel] = {m.slug: m for m in _MODELS}

SUPPORTED_LOCAL_ASR_MODELS: set[str] = frozenset(_BY_SLUG.keys())


def list_local_asr_models() -> list[AsrModel]:
    """Return all supported local ASR models."""
    return list(_MODELS)


def get_local_asr_model(slug: str) -> AsrModel:
    """Return the AsrModel for *slug*, or raise KeyError."""
    return _BY_SLUG[slug]
