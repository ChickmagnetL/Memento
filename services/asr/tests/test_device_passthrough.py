"""Test that device is passed through to the ASR transcribers."""
import sys
from pathlib import Path
from types import SimpleNamespace

ASR_SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(ASR_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(ASR_SERVICE_DIR))


def test_funasr_transcriber_receives_device_and_passes_to_automodel(monkeypatch):
    """FunAsrTranscriber must accept device= and pass it to AutoModel."""
    from transcribers import FunAsrTranscriber

    captured_device = None

    class FakeAutoModel:
        def __init__(self, model, device, disable_update):
            nonlocal captured_device
            captured_device = device

        def generate(self, input, fs, use_itn):
            return [{"text": "hello"}]

    monkeypatch.setitem(sys.modules, "funasr", type(sys)("funasr"))
    sys.modules["funasr"].AutoModel = FakeAutoModel
    sys.modules["funasr"].utils = type(sys)("utils")
    sys.modules["funasr"].utils.postprocess_utils = type(sys)("postprocess_utils")
    sys.modules["funasr"].utils.postprocess_utils.rich_transcription_postprocess = lambda x: x

    tc = FunAsrTranscriber(model="iic/SenseVoiceSmall", device="cuda")
    assert captured_device == "cuda", f"Expected 'cuda', got {captured_device!r}"


def test_funasr_transcriber_defaults_device_to_cpu_when_omitted(monkeypatch):
    """FunAsrTranscriber must default device='cpu' when not specified."""
    from transcribers import FunAsrTranscriber

    captured_device = None

    class FakeAutoModel:
        def __init__(self, model, device, disable_update):
            nonlocal captured_device
            captured_device = device

        def generate(self, input, fs, use_itn):
            return [{"text": "hello"}]

    monkeypatch.setitem(sys.modules, "funasr", type(sys)("funasr"))
    sys.modules["funasr"].AutoModel = FakeAutoModel
    sys.modules["funasr"].utils = type(sys)("utils")
    sys.modules["funasr"].utils.postprocess_utils = type(sys)("postprocess_utils")
    sys.modules["funasr"].utils.postprocess_utils.rich_transcription_postprocess = lambda x: x

    tc = FunAsrTranscriber(model="iic/SenseVoiceSmall")
    assert captured_device == "cpu", f"Expected 'cpu', got {captured_device!r}"


def test_moonshine_transcriber_receives_device(monkeypatch):
    """MoonshineVoiceTranscriber must accept and store device=."""
    from transcribers import MoonshineVoiceTranscriber

    class FakeTranscriber:
        def __init__(self, model_path, model_arch):
            pass
        def transcribe_without_streaming(self, audio, sample_rate):
            return []

    def fake_get_model(wanted_language, wanted_model_arch):
        return ("/fake/path", wanted_model_arch)

    fake_moonshine = type(sys)("moonshine_voice")
    fake_moonshine.ModelArch = type("ModelArch", (), {"MEDIUM_STREAMING": "medium_streaming"})()
    fake_moonshine.Transcriber = FakeTranscriber
    fake_moonshine.get_model_for_language = fake_get_model
    monkeypatch.setitem(sys.modules, "moonshine_voice", fake_moonshine)
    monkeypatch.setattr("transcribers.MoonshineVoiceTranscriber", MoonshineVoiceTranscriber)

    tc = MoonshineVoiceTranscriber(model="moonshine_voice/medium-streaming-en", device="cuda")
    assert tc.device == "cuda"


def test_moonshine_transcriber_defaults_device_to_cpu(monkeypatch):
    """MoonshineVoiceTranscriber must default device='cpu' when omitted."""
    from transcribers import MoonshineVoiceTranscriber

    class FakeTranscriber:
        def __init__(self, model_path, model_arch):
            pass
        def transcribe_without_streaming(self, audio, sample_rate):
            return []

    def fake_get_model(wanted_language, wanted_model_arch):
        return ("/fake/path", wanted_model_arch)

    fake_moonshine = type(sys)("moonshine_voice")
    fake_moonshine.ModelArch = type("ModelArch", (), {"MEDIUM_STREAMING": "medium_streaming"})()
    fake_moonshine.Transcriber = FakeTranscriber
    fake_moonshine.get_model_for_language = fake_get_model
    monkeypatch.setitem(sys.modules, "moonshine_voice", fake_moonshine)
    monkeypatch.setattr("transcribers.MoonshineVoiceTranscriber", MoonshineVoiceTranscriber)

    tc = MoonshineVoiceTranscriber(model="moonshine_voice/medium-streaming-en")
    assert tc.device == "cpu"


def test_server_get_transcriber_passes_device_from_env(monkeypatch):
    """server.get_transcriber reads ASR_DEVICE env var and passes device to transcriber."""
    import server

    server._transcribers.clear()
    monkeypatch.setenv("ASR_DEVICE", "cuda")

    captured_device = None

    class FakeTranscriber:
        def __init__(self, model, device):
            nonlocal captured_device
            captured_device = device

    monkeypatch.setattr(server, "_get_transcriber_class", lambda m: FakeTranscriber)

    tc = server.get_transcriber("iic/SenseVoiceSmall")
    assert captured_device == "cuda", f"Expected 'cuda', got {captured_device!r}"


def test_server_get_transcriber_auto_detects_device_when_env_is_unset(monkeypatch):
    """server.get_transcriber auto-detects the runtime device without ASR_DEVICE."""
    import server

    server._transcribers.clear()
    monkeypatch.delenv("ASR_DEVICE", raising=False)
    monkeypatch.setattr(server, "detect_best_device", lambda: "mps")

    captured_device = None

    class FakeTranscriber:
        def __init__(self, model, device):
            nonlocal captured_device
            captured_device = device

    monkeypatch.setattr(server, "_get_transcriber_class", lambda m: FakeTranscriber)

    tc = server.get_transcriber("iic/SenseVoiceSmall")
    assert captured_device == "mps", f"Expected 'mps', got {captured_device!r}"


def test_server_detect_best_device_prefers_cuda(monkeypatch):
    """Runtime detection uses CUDA when the service torch supports it."""
    import server

    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: True),
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: True)),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    assert server.detect_best_device() == "cuda"


def test_server_detect_best_device_uses_mps_without_cuda(monkeypatch):
    """Runtime detection uses MPS when CUDA is unavailable."""
    import server

    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False),
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: True)),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    assert server.detect_best_device() == "mps"


def test_detect_best_device_prefers_nvidia_before_asr_venv_exists(monkeypatch):
    """A clean Settings deploy must detect NVIDIA without relying on venv torch."""
    import deploy

    monkeypatch.setattr(
        deploy.shutil,
        "which",
        lambda name: "/usr/bin/nvidia-smi" if name == "nvidia-smi" else None,
    )
    monkeypatch.setattr(
        deploy.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("venv torch should not be probed before NVIDIA detection")
        ),
    )

    assert deploy.detect_best_device() == "cuda"


def test_detect_best_device_uses_mps_on_macos_before_asr_venv_exists(monkeypatch):
    """A clean Settings deploy must select MPS on macOS without an ASR venv."""
    import deploy

    monkeypatch.setattr(deploy.shutil, "which", lambda name: None)
    monkeypatch.setattr(deploy.sys, "platform", "darwin")
    monkeypatch.setattr(
        deploy.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("venv torch should not be probed before macOS detection")
        ),
    )

    assert deploy.detect_best_device() == "mps"


def test_detect_best_device_returns_valid_device():
    """detect_best_device must return one of 'cuda', 'mps', 'cpu'."""
    from deploy import detect_best_device
    device = detect_best_device()
    assert device in ("cuda", "mps", "cpu"), f"Unexpected device: {device!r}"
