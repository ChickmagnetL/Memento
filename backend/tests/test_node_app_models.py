# backend/tests/test_node_app_models.py
import importlib.util
import sys
from pathlib import Path

NODE_APP = Path(__file__).resolve().parents[2] / "services" / "node" / "node_app"


def _load_models():
    # Always re-exec so edits are picked up without stale sys.modules
    for name in ("node_app_models", "node_app_paths"):
        if name in sys.modules:
            del sys.modules[name]
    for name, file in (("node_app_paths", "paths.py"), ("node_app_models", "models.py")):
        p = NODE_APP / file
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        assert spec.loader is not None
        spec.loader.exec_module(mod)
    return sys.modules["node_app_models"]


def test_asr_catalog_includes_sensevoice_and_five_moonshine():
    m = _load_models()
    slugs = {x.slug for x in m.ASR_MODELS}
    assert "sensevoice-small" in slugs
    assert "moonshine-medium-streaming-en" in slugs
    assert len(m.ASR_MODELS) == 6


def test_embedding_catalog_has_bge_and_qwen_no_minilm():
    m = _load_models()
    model_ids = {x.model_id for x in m.EMBEDDING_MODELS}
    slugs = {x.slug for x in m.EMBEDDING_MODELS}
    assert "BAAI/bge-m3" in model_ids
    assert "Qwen/Qwen3-Embedding-0.6B" in model_ids
    assert "bge-m3" in slugs
    assert "qwen3-embedding-0.6b" in slugs
    assert not any("minilm" in x.model_id.lower() for x in m.EMBEDDING_MODELS)
    assert not any("minilm" in x.slug.lower() for x in m.EMBEDDING_MODELS)
    assert len(m.EMBEDDING_MODELS) == 2


def test_sensevoice_installed_false_on_empty_tmp(tmp_path, monkeypatch):
    m = _load_models()
    monkeypatch.setattr(m, "ASR_DIR", tmp_path / "asr")
    (tmp_path / "asr" / "models").mkdir(parents=True)
    status = m.check_asr_models()
    assert status["sensevoice-small"] is False


def test_embedding_cache_dir_format(tmp_path):
    m = _load_models()
    p = m.embedding_cache_dir(tmp_path, "BAAI/bge-m3")
    assert p == tmp_path / "models" / "models--BAAI--bge-m3"
    p2 = m.embedding_cache_dir(tmp_path, "Qwen/Qwen3-Embedding-0.6B")
    assert p2 == tmp_path / "models" / "models--Qwen--Qwen3-Embedding-0.6B"


def test_check_embedding_models_with_tmp(tmp_path):
    m = _load_models()
    emb = tmp_path / "embedding"
    status = m.check_embedding_models(emb)
    assert status["bge-m3"] is False
    assert status["qwen3-embedding-0.6b"] is False

    # Empty dir is not installed
    (emb / "models" / "models--BAAI--bge-m3").mkdir(parents=True)
    status = m.check_embedding_models(emb)
    assert status["bge-m3"] is False
    assert status["qwen3-embedding-0.6b"] is False

    # Config-only / dummy file is incomplete
    (emb / "models" / "models--BAAI--bge-m3" / "dummy.txt").write_text("x", encoding="utf-8")
    status = m.check_embedding_models(emb)
    assert status["bge-m3"] is False

    # Tiny weight file does NOT count as installed
    nested = emb / "models" / "models--BAAI--bge-m3" / "snapshots" / "abc"
    nested.mkdir(parents=True)
    (nested / "model.safetensors").write_bytes(b"weights")
    status = m.check_embedding_models(emb)
    assert status["bge-m3"] is False

    # Large weight file counts as installed
    (nested / "model.safetensors").write_bytes(b"x" * 1_000_001)
    status = m.check_embedding_models(emb)
    assert status["bge-m3"] is True
    assert status["qwen3-embedding-0.6b"] is False


def test_uninstall_embedding_model_removes_cache(tmp_path):
    m = _load_models()
    emb = tmp_path / "embedding"
    cache = emb / "models" / "models--BAAI--bge-m3"
    cache.mkdir(parents=True)
    (cache / "config.json").write_text("{}", encoding="utf-8")
    # venv must never be touched
    venv = emb / ".venv"
    venv.mkdir()
    (venv / "marker").write_text("keep", encoding="utf-8")

    assert m.uninstall_embedding_model("bge-m3", emb) is True
    assert not cache.exists()
    assert (venv / "marker").read_text(encoding="utf-8") == "keep"
    assert m.uninstall_embedding_model("bge-m3", emb) is False


def test_uninstall_asr_sensevoice_and_moonshine(tmp_path):
    m = _load_models()
    asr = tmp_path / "asr"
    sense = asr / "models" / "sensevoice"
    sense.mkdir(parents=True)
    (sense / "model.pt").write_text("x", encoding="utf-8")

    moon = (
        asr / "models" / "moonshine" / "download.moonshine.ai"
        / "model" / "tiny-en" / "quantized"
    )
    moon.mkdir(parents=True)
    (moon / "weights.bin").write_text("x", encoding="utf-8")
    other = (
        asr / "models" / "moonshine" / "download.moonshine.ai"
        / "model" / "base-en" / "quantized"
    )
    other.mkdir(parents=True)
    venv = asr / ".venv"
    venv.mkdir()
    (venv / "marker").write_text("keep", encoding="utf-8")

    assert m.uninstall_asr_model("sensevoice-small", asr) is True
    assert not sense.exists()
    assert m.uninstall_asr_model("sensevoice-small", asr) is False

    assert m.uninstall_asr_model("moonshine-tiny-en", asr) is True
    assert not (asr / "models" / "moonshine" / "download.moonshine.ai" / "model" / "tiny-en").exists()
    # other moonshine model untouched
    assert other.is_dir()
    assert (venv / "marker").read_text(encoding="utf-8") == "keep"


def test_embedding_by_slug():
    m = _load_models()
    spec = m.embedding_by_slug("bge-m3")
    assert spec.model_id == "BAAI/bge-m3"
    try:
        m.embedding_by_slug("no-such")
        assert False, "expected KeyError"
    except KeyError:
        pass



def test_embedding_index_only_not_installed(tmp_path):
    m = _load_models()
    emb = tmp_path / "embedding"
    nested = emb / "models" / "models--BAAI--bge-m3" / "snapshots" / "abc"
    nested.mkdir(parents=True)
    (nested / "model.safetensors.index.json").write_text("{}", encoding="utf-8")
    status = m.check_embedding_models(emb)
    assert status["bge-m3"] is False



def test_uninstall_embedding_model_removes_both_candidate_dirs(tmp_path):
    m = _load_models()
    emb = tmp_path / "embedding"
    direct = emb / "models" / "models--BAAI--bge-m3"
    st = emb / "models" / "models--sentence-transformers--BAAI--bge-m3"
    direct.mkdir(parents=True)
    st.mkdir(parents=True)
    (direct / "config.json").write_text("{}", encoding="utf-8")
    (st / "config.json").write_text("{}", encoding="utf-8")
    venv = emb / ".venv"
    venv.mkdir()
    (venv / "marker").write_text("keep", encoding="utf-8")

    assert m.uninstall_embedding_model("bge-m3", emb) is True
    assert not direct.exists()
    assert not st.exists()
    assert (venv / "marker").read_text(encoding="utf-8") == "keep"
    assert m.uninstall_embedding_model("bge-m3", emb) is False
