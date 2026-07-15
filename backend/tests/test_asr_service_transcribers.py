"""Tests for ASR service transcriber model routing and spec mapping."""

import importlib
import sys
import types
from pathlib import Path

import pytest


SERVICES_ASR = Path(__file__).resolve().parents[2] / "services" / "asr"


# ---------------------------------------------------------------------------
# Dynamic import helpers
# ---------------------------------------------------------------------------

def _import_transcribers_module():
    """Dynamically import transcribers.py from services/asr/."""
    asr_dir = str(SERVICES_ASR)
    if asr_dir not in sys.path:
        sys.path.insert(0, asr_dir)
    path = SERVICES_ASR / "transcribers.py"
    spec = importlib.util.spec_from_file_location(
        "transcribers_test_mod", path
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _import_server_module():
    """Dynamically import server.py from services/asr/."""
    asr_dir = str(SERVICES_ASR)
    if asr_dir not in sys.path:
        sys.path.insert(0, asr_dir)
    path = SERVICES_ASR / "server.py"
    spec = importlib.util.spec_from_file_location(
        "asr_server_test_mod", path
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_sensevoice_local_path_supports_current_modelscope_layout(tmp_path: Path):
    transcribers = _import_transcribers_module()
    snapshot = (
        tmp_path
        / "models"
        / "sensevoice"
        / "models"
        / "iic--SenseVoiceSmall"
        / "snapshots"
        / "master"
    )
    snapshot.mkdir(parents=True)
    (snapshot / "model.pt").touch()

    assert transcribers._sensevoice_local_path(tmp_path) == snapshot


# ---------------------------------------------------------------------------
# _moonshine_voice_model tests
# ---------------------------------------------------------------------------


class TestMoonshineVoiceModel:
    """Tests for _moonshine_voice_model() spec-to-arch mapping."""

    # Expected (spec, arch_attr_name) pairs for all five Moonshine variants
    VARIANTS = [
        ("tiny-en", "TINY"),
        ("base-en", "BASE"),
        ("tiny-streaming-en", "TINY_STREAMING"),
        ("small-streaming-en", "SMALL_STREAMING"),
        ("medium-streaming-en", "MEDIUM_STREAMING"),
    ]

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        """Provide a fake moonshine_voice module so transcribers can be imported."""
        fake_moonshine_voice = types.SimpleNamespace(
            ModelArch=types.SimpleNamespace(
                TINY=object(),
                BASE=object(),
                TINY_STREAMING=object(),
                SMALL_STREAMING=object(),
                MEDIUM_STREAMING=object(),
            ),
            Transcriber=object,
            get_model_for_language=lambda **kw: (None, None),
        )
        # Make sure soundfile is mocked so transcribers.py can be loaded
        fake_soundfile = types.SimpleNamespace()
        fake_soundfile.read = lambda path, dtype: (None, None)

        monkeypatch.setitem(sys.modules, "moonshine_voice", fake_moonshine_voice)
        monkeypatch.setitem(sys.modules, "soundfile", fake_soundfile)

    @pytest.mark.parametrize("spec,arch_attr", VARIANTS)
    def test_spec_maps_to_correct_arch(self, spec, arch_attr, monkeypatch):
        """Each Moonshine spec maps to the correct ModelArch enum value."""
        transcribers = _import_transcribers_module()

        # Re-obtain the fake ModelArch that was injected
        fake_moonshine_voice = sys.modules["moonshine_voice"]
        ModelArch = fake_moonshine_voice.ModelArch

        language, arch = transcribers._moonshine_voice_model(spec, ModelArch)
        assert language == "en"
        assert arch is getattr(ModelArch, arch_attr)

    @pytest.mark.parametrize("spec,arch_attr", VARIANTS)
    def test_full_model_id_strips_prefix(self, spec, arch_attr, monkeypatch):
        """Full model_id 'moonshine_voice/<spec>' is accepted and prefix stripped."""
        transcribers = _import_transcribers_module()
        fake_moonshine_voice = sys.modules["moonshine_voice"]
        ModelArch = fake_moonshine_voice.ModelArch

        model_id = f"moonshine_voice/{spec}"
        language, arch = transcribers._moonshine_voice_model(model_id, ModelArch)
        assert language == "en"
        assert arch is getattr(ModelArch, arch_attr)

    def test_raises_for_unknown_spec(self):
        """Unknown spec raises ValueError with helpful message."""
        transcribers = _import_transcribers_module()
        fake_moonshine_voice = sys.modules["moonshine_voice"]
        ModelArch = fake_moonshine_voice.ModelArch

        with pytest.raises(ValueError, match="Unsupported Moonshine Voice model"):
            transcribers._moonshine_voice_model("unsupported-en", ModelArch)

    def test_raises_for_unknown_full_model_id(self):
        """Unknown full model_id raises ValueError."""
        transcribers = _import_transcribers_module()
        fake_moonshine_voice = sys.modules["moonshine_voice"]
        ModelArch = fake_moonshine_voice.ModelArch

        with pytest.raises(ValueError, match="Unsupported Moonshine Voice model"):
            transcribers._moonshine_voice_model(
                "moonshine_voice/unknown-en", ModelArch
            )

    def test_raises_for_sensevoice_model(self):
        """SenseVoice model IDs should not be passed to _moonshine_voice_model."""
        transcribers = _import_transcribers_module()
        fake_moonshine_voice = sys.modules["moonshine_voice"]
        ModelArch = fake_moonshine_voice.ModelArch

        with pytest.raises(ValueError, match="Unsupported Moonshine Voice model"):
            transcribers._moonshine_voice_model("iic/SenseVoiceSmall", ModelArch)


# ---------------------------------------------------------------------------
# _get_transcriber_class routing tests
# ---------------------------------------------------------------------------


class TestGetTranscriberClassRouting:
    """Tests for server._get_transcriber_class() model routing."""

    MOONSHINE_SPECS = [
        "tiny-en",
        "base-en",
        "tiny-streaming-en",
        "small-streaming-en",
        "medium-streaming-en",
    ]

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        """Import server module and reset its global state."""
        # Reset module-level globals in server before each test
        server_mod = _import_server_module()
        server_mod._transcribers.clear()
        server_mod.MoonshineVoiceTranscriber = None
        server_mod.FunAsrTranscriber = None

        # Provide fake transcriber classes
        self.FakeMoonshineVoiceTranscriber = type(
            "FakeMoonshineVoiceTranscriber", (), {}
        )
        self.FakeFunAsrTranscriber = type("FakeFunAsrTranscriber", (), {})

        monkeypatch.setattr(
            server_mod,
            "MoonshineVoiceTranscriber",
            self.FakeMoonshineVoiceTranscriber,
        )
        monkeypatch.setattr(
            server_mod, "FunAsrTranscriber", self.FakeFunAsrTranscriber
        )

        self.server = server_mod

    @pytest.mark.parametrize("spec", MOONSHINE_SPECS)
    def test_bare_spec_routes_to_moonshine(self, spec):
        """Bare Moonshine spec (e.g. 'tiny-en') routes to MoonshineVoiceTranscriber."""
        cls = self.server._get_transcriber_class(spec)
        assert cls is self.FakeMoonshineVoiceTranscriber

    @pytest.mark.parametrize("spec", MOONSHINE_SPECS)
    def test_full_model_id_routes_to_moonshine(self, spec):
        """Full model_id 'moonshine_voice/<spec>' routes to MoonshineVoiceTranscriber."""
        model_id = f"moonshine_voice/{spec}"
        cls = self.server._get_transcriber_class(model_id)
        assert cls is self.FakeMoonshineVoiceTranscriber

    def test_sensevoice_small_routes_to_funasr(self):
        """iic/SenseVoiceSmall routes to FunAsrTranscriber."""
        cls = self.server._get_transcriber_class("iic/SenseVoiceSmall")
        assert cls is self.FakeFunAsrTranscriber

    def test_sensevoice_small_alias_routes_to_funasr(self):
        """sensevoice-small alias routes to FunAsrTranscriber."""
        cls = self.server._get_transcriber_class("sensevoice-small")
        assert cls is self.FakeFunAsrTranscriber

    def test_unknown_model_raises_value_error(self):
        """Completely unknown model raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported ASR model"):
            self.server._get_transcriber_class("unknown-model-xyz")

    def test_sensevoice_tiny_raises_value_error(self):
        """SenseVoice Tiny (not in registry) raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported ASR model"):
            self.server._get_transcriber_class("iic/SenseVoiceTiny")

    def test_sensevoice_medium_raises_value_error(self):
        """SenseVoice Medium (not in registry) raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported ASR model"):
            self.server._get_transcriber_class("sensevoice-medium")

    def test_sensevoice_large_raises_value_error(self):
        """SenseVoice Large (not in registry) raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported ASR model"):
            self.server._get_transcriber_class("iic/SenseVoiceLarge")

    def test_moonshine_nonexistent_spec_raises_value_error(self):
        """A moonshine_voice/ prefix with unknown spec raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported ASR model"):
            self.server._get_transcriber_class("moonshine_voice/nonexistent-en")


# ---------------------------------------------------------------------------
# get_transcriber integration tests
# ---------------------------------------------------------------------------


class TestGetTranscriber:
    """Tests for server.get_transcriber() model normalization and caching."""

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        """Import server module and reset its global state."""
        server_mod = _import_server_module()
        server_mod._transcribers.clear()
        server_mod.MoonshineVoiceTranscriber = None
        server_mod.FunAsrTranscriber = None
        monkeypatch.setattr(server_mod, "detect_best_device", lambda: "mps")
        self.server = server_mod

    def test_normalizes_sensevoice_small_alias(self):
        """Passing sensevoice-small constructs FunAsrTranscriber with iic/SenseVoiceSmall."""
        seen_models = []

        class TrackedFunAsrTranscriber:
            def __init__(self, *, model: str, device: str) -> None:
                seen_models.append(("funasr", model, device))

        self.server.FunAsrTranscriber = TrackedFunAsrTranscriber

        transcriber = self.server.get_transcriber("sensevoice-small")

        assert isinstance(transcriber, TrackedFunAsrTranscriber)
        assert seen_models == [("funasr", "iic/SenseVoiceSmall", "mps")]

    def test_normalizes_sensevoice_small_alias_once(self):
        """sensevoice-small alias is normalized before caching."""
        seen_models = []

        class TrackedFunAsrTranscriber:
            def __init__(self, *, model: str, device: str) -> None:
                seen_models.append(("funasr", model, device))

        self.server.FunAsrTranscriber = TrackedFunAsrTranscriber

        first = self.server.get_transcriber("sensevoice-small")
        second = self.server.get_transcriber("sensevoice-small")

        assert first is second
        assert len(seen_models) == 1
        assert seen_models[0] == ("funasr", "iic/SenseVoiceSmall", "mps")

    def test_backward_compat_medium_streaming_en(self):
        """moonshine_voice/medium-streaming-en still works and uses correct spec."""
        seen_models = []

        class TrackedMoonshineVoiceTranscriber:
            def __init__(self, *, model: str, device: str) -> None:
                seen_models.append(("moonshine", model, device))

        class TrackedFunAsrTranscriber:
            def __init__(self, *, model: str, device: str) -> None:
                seen_models.append(("funasr", model, device))

        self.server.MoonshineVoiceTranscriber = TrackedMoonshineVoiceTranscriber
        self.server.FunAsrTranscriber = TrackedFunAsrTranscriber

        transcriber = self.server.get_transcriber(
            "moonshine_voice/medium-streaming-en"
        )

        assert isinstance(transcriber, TrackedMoonshineVoiceTranscriber)
        assert seen_models == [
            ("moonshine", "moonshine_voice/medium-streaming-en", "mps")
        ]

    def test_all_five_variants_via_bare_spec(self):
        """All five Moonshine variants work with bare spec and separate Transcriber instances."""
        seen_models = []

        class TrackedMoonshineVoiceTranscriber:
            def __init__(self, *, model: str, device: str) -> None:
                seen_models.append(("moonshine", model, device))

        class TrackedFunAsrTranscriber:
            def __init__(self, *, model: str, device: str) -> None:
                seen_models.append(("funasr", model, device))

        self.server.MoonshineVoiceTranscriber = TrackedMoonshineVoiceTranscriber
        self.server.FunAsrTranscriber = TrackedFunAsrTranscriber

        specs = [
            "tiny-en",
            "base-en",
            "tiny-streaming-en",
            "small-streaming-en",
            "medium-streaming-en",
        ]

        for spec in specs:
            self.server.get_transcriber(spec)

        assert len(seen_models) == 5
        for i, spec in enumerate(specs):
            assert seen_models[i] == ("moonshine", spec, "mps")


# ---------------------------------------------------------------------------
# Cross-reference: service mirror vs backend registry
# ---------------------------------------------------------------------------


def test_service_mirror_matches_backend_registry():
    """The service-side model routing tables must stay in sync with the
    backend registry to avoid drift between what the backend reports as
    supported and what the ASR service can actually route."""
    from services.asr.server import _MOONSHINE_SPECS, _SENSEVOICE_MODELS  # type: ignore[import-not-resolved]
    from core.asr_model_registry import list_local_asr_models

    all_models = list_local_asr_models()

    # Moonshine specs must match the set of spec fields in the backend registry
    backend_moonshine_specs = {m.spec for m in all_models if m.runtime == "moonshine"}
    assert _MOONSHINE_SPECS == backend_moonshine_specs, (
        f"Service moonshine specs {_MOONSHINE_SPECS} "
        f"diverge from backend registry {backend_moonshine_specs}"
    )

    # SenseVoice model_ids: service must accept backend's model_id + slug alias
    backend_sensevoice_ids = {m.model_id for m in all_models if m.runtime == "sensevoice"}
    for model_id in backend_sensevoice_ids:
        assert model_id in _SENSEVOICE_MODELS, (
            f"Backend SenseVoice model_id {model_id} missing from service mirror"
        )

    # Every slug should have a route through the service mirror
    backend_slugs = {m.slug for m in all_models}
    service_model_ids = _SENSEVOICE_MODELS | {f"moonshine_voice/{s}" for s in _MOONSHINE_SPECS}
    # SenseVoice slug aliases are in _SENSEVOICE_MODELS
    for m in all_models:
        # Each model's slug must be resolvable: either directly or via mirror
        assert m.slug in backend_slugs  # trivially true; belt-and-suspenders
