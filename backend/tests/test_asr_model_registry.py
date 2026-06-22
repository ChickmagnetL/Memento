"""Tests for local ASR model registry."""

import pytest

from core.asr_model_registry import (
    AsrModel,
    SUPPORTED_LOCAL_ASR_MODELS,
    get_local_asr_model,
    list_local_asr_models,
)


def test_registry_contains_exactly_six_models():
    models = list_local_asr_models()
    assert len(models) == 6, f"Expected 6 models, got {len(models)}"


def test_all_slugs_are_unique():
    models = list_local_asr_models()
    slugs = [m.slug for m in models]
    assert len(slugs) == len(set(slugs))


def test_all_model_ids_are_unique():
    models = list_local_asr_models()
    ids = [m.model_id for m in models]
    assert len(ids) == len(set(ids))


def test_sensevoice_small_present():
    model = get_local_asr_model("sensevoice-small")
    assert model.family == "sensevoice"
    assert model.label == "SenseVoice Small"
    assert model.model_id == "iic/SenseVoiceSmall"
    assert model.size == "0.9GB"
    assert model.runtime == "sensevoice"
    assert model.spec is None


def test_sensevoice_only_has_small_not_other_sizes():
    models = list_local_asr_models()
    sensevoice_models = [m for m in models if m.family == "sensevoice"]
    assert len(sensevoice_models) == 1
    assert sensevoice_models[0].model_id == "iic/SenseVoiceSmall"


def test_moonshine_tiny_en():
    model = get_local_asr_model("moonshine-tiny-en")
    assert model.family == "moonshine"
    assert model.model_id == "moonshine_voice/tiny-en"
    assert model.spec == "tiny-en"
    assert model.size == "71MB"
    assert model.runtime == "moonshine"


def test_moonshine_base_en():
    model = get_local_asr_model("moonshine-base-en")
    assert model.family == "moonshine"
    assert model.model_id == "moonshine_voice/base-en"
    assert model.spec == "base-en"
    assert model.size == "238MB"
    assert model.runtime == "moonshine"


def test_moonshine_tiny_streaming_en():
    model = get_local_asr_model("moonshine-tiny-streaming-en")
    assert model.family == "moonshine"
    assert model.model_id == "moonshine_voice/tiny-streaming-en"
    assert model.spec == "tiny-streaming-en"
    assert model.size == "80MB"
    assert model.runtime == "moonshine"


def test_moonshine_small_streaming_en():
    model = get_local_asr_model("moonshine-small-streaming-en")
    assert model.family == "moonshine"
    assert model.model_id == "moonshine_voice/small-streaming-en"
    assert model.spec == "small-streaming-en"
    assert model.size == "235MB"
    assert model.runtime == "moonshine"


def test_moonshine_medium_streaming_en():
    model = get_local_asr_model("moonshine-medium-streaming-en")
    assert model.family == "moonshine"
    assert model.model_id == "moonshine_voice/medium-streaming-en"
    assert model.spec == "medium-streaming-en"
    assert model.size == "429MB"
    assert model.runtime == "moonshine"


def test_moonshine_has_five_variants():
    models = list_local_asr_models()
    moonshine_models = [m for m in models if m.family == "moonshine"]
    assert len(moonshine_models) == 5


def test_get_local_asr_model_raises_keyerror_for_unknown_slug():
    with pytest.raises(KeyError):
        get_local_asr_model("nonexistent-model")


def test_supported_local_asr_models_matches_list():
    models = list_local_asr_models()
    assert set(SUPPORTED_LOCAL_ASR_MODELS) == {m.slug for m in models}
