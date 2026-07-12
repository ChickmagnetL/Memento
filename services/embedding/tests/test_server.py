"""Tests for the standalone embedding service."""
import sys
from pathlib import Path
from unittest.mock import MagicMock


import numpy as np
from fastapi.testclient import TestClient

import server


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        client = TestClient(server.app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestModelsEndpoint:
    def test_models_returns_data_with_ids(self, monkeypatch):
        monkeypatch.setattr(server, "_embedding_installed", lambda model_id: True)
        client = TestClient(server.app)
        response = client.get("/v1/models")
        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        assert isinstance(body["data"], list)
        assert len(body["data"]) > 0
        for item in body["data"]:
            assert "id" in item
            assert isinstance(item["id"], str)

    def test_models_returns_both_catalog_ids_when_installed(self, monkeypatch):
        monkeypatch.setattr(server, "_embedding_installed", lambda model_id: True)
        client = TestClient(server.app)
        response = client.get("/v1/models")
        assert response.status_code == 200
        ids = [item["id"] for item in response.json()["data"]]
        assert ids == ["BAAI/bge-m3", "Qwen/Qwen3-Embedding-0.6B"]

    def test_models_empty_when_none_installed(self, monkeypatch):
        monkeypatch.setattr(server, "_embedding_installed", lambda model_id: False)
        client = TestClient(server.app)
        response = client.get("/v1/models")
        assert response.status_code == 200
        assert response.json() == {"data": []}


class TestEmbeddingsEndpoint:
    def test_embeddings_returns_data_with_index_and_embedding(self, monkeypatch):
        """POST /v1/embeddings returns matching OpenAI-compatible shape."""
        class FakeModel:
            def encode(self, input, normalize_embeddings=True, **kwargs):
                return np.array([[0.1, 0.2, 0.3] for _ in input])

        monkeypatch.setattr(server, "_load_model", lambda model_id: FakeModel())

        client = TestClient(server.app)
        response = client.post(
            "/v1/embeddings",
            json={"model": "BAAI/bge-m3", "input": ["hello", "world"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        assert len(body["data"]) == 2
        assert body["data"][0]["index"] == 0
        assert body["data"][0]["embedding"] == [0.1, 0.2, 0.3]
        assert body["data"][1]["index"] == 1
        assert body["data"][1]["embedding"] == [0.1, 0.2, 0.3]
        assert body["model"] == "BAAI/bge-m3"

    def test_embeddings_uses_requested_model(self, monkeypatch):
        """POST /v1/embeddings passes the model name to _load_model."""
        seen_model = None

        class FakeModel:
            def encode(self, input, normalize_embeddings=True, **kwargs):
                return np.array([[0.0] for _ in input])

        def fake_load_model(model_id):
            nonlocal seen_model
            seen_model = model_id
            return FakeModel()

        monkeypatch.setattr(server, "_load_model", fake_load_model)

        client = TestClient(server.app)
        response = client.post(
            "/v1/embeddings",
            json={"model": "custom-model", "input": ["test"]},
        )
        assert response.status_code == 200
        assert seen_model == "custom-model"

    def test_embeddings_defaults_model(self, monkeypatch):
        """POST /v1/embeddings defaults model when omitted."""
        seen_model = None

        class FakeModel:
            def encode(self, input, normalize_embeddings=True, **kwargs):
                return np.array([[0.0] for _ in input])

        def fake_load_model(model_id):
            nonlocal seen_model
            seen_model = model_id
            return FakeModel()

        monkeypatch.setattr(server, "_load_model", fake_load_model)

        client = TestClient(server.app)
        response = client.post("/v1/embeddings", json={"input": ["test"]})
        assert response.status_code == 200
        assert seen_model == "BAAI/bge-m3"

    def test_embeddings_model_load_failure_returns_500(self, monkeypatch):
        """POST /v1/embeddings returns 500 when model fails to load."""
        def fake_load_model(model_id):
            raise RuntimeError("GPU out of memory")

        monkeypatch.setattr(server, "_load_model", fake_load_model)

        client = TestClient(server.app)
        response = client.post(
            "/v1/embeddings",
            json={"model": "bad-model", "input": ["test"]},
        )
        assert response.status_code == 500
        detail = response.json()["detail"]
        assert "bad-model" in detail
        assert "GPU out of memory" in detail

    def test_embeddings_inference_failure_returns_500(self, monkeypatch):
        """POST /v1/embeddings returns 500 when encode fails."""
        class FakeModel:
            def encode(self, input, normalize_embeddings=True, **kwargs):
                raise RuntimeError("CUDA error")

        monkeypatch.setattr(server, "_load_model", lambda model_id: FakeModel())

        client = TestClient(server.app)
        response = client.post(
            "/v1/embeddings",
            json={"model": "BAAI/bge-m3", "input": ["test"]},
        )
        assert response.status_code == 500
        detail = response.json()["detail"]
        assert "Embedding inference failed" in detail

    def test_qwen_query_encode_uses_prompt_name(self, monkeypatch):
        """Qwen + input_type=query passes prompt_name='query'."""
        seen_kwargs = {}

        class FakeModel:
            def encode(self, input, **kwargs):
                seen_kwargs.update(kwargs)
                return np.array([[0.0] for _ in input])

        monkeypatch.setattr(server, "_load_model", lambda model_id: FakeModel())

        client = TestClient(server.app)
        response = client.post(
            "/v1/embeddings",
            json={
                "model": "Qwen/Qwen3-Embedding-0.6B",
                "input": ["search query"],
                "input_type": "query",
            },
        )
        assert response.status_code == 200
        assert seen_kwargs.get("prompt_name") == "query"
        assert seen_kwargs.get("normalize_embeddings") is True

    def test_qwen_document_encode_no_prompt_name(self, monkeypatch):
        """Qwen + input_type=document does not pass prompt_name."""
        seen_kwargs = {}

        class FakeModel:
            def encode(self, input, **kwargs):
                seen_kwargs.update(kwargs)
                return np.array([[0.0] for _ in input])

        monkeypatch.setattr(server, "_load_model", lambda model_id: FakeModel())

        client = TestClient(server.app)
        response = client.post(
            "/v1/embeddings",
            json={
                "model": "Qwen/Qwen3-Embedding-0.6B",
                "input": ["document text"],
                "input_type": "document",
            },
        )
        assert response.status_code == 200
        assert "prompt_name" not in seen_kwargs
        assert seen_kwargs.get("normalize_embeddings") is True

    def test_qwen_missing_input_type_no_prompt_name(self, monkeypatch):
        """Qwen without input_type does not pass prompt_name."""
        seen_kwargs = {}

        class FakeModel:
            def encode(self, input, **kwargs):
                seen_kwargs.update(kwargs)
                return np.array([[0.0] for _ in input])

        monkeypatch.setattr(server, "_load_model", lambda model_id: FakeModel())

        client = TestClient(server.app)
        response = client.post(
            "/v1/embeddings",
            json={
                "model": "Qwen/Qwen3-Embedding-0.6B",
                "input": ["document text"],
            },
        )
        assert response.status_code == 200
        assert "prompt_name" not in seen_kwargs
        assert seen_kwargs.get("normalize_embeddings") is True

    def test_non_qwen_never_passes_prompt_name(self, monkeypatch):
        """Non-Qwen models never pass prompt_name even with input_type=query."""
        seen_kwargs = {}

        class FakeModel:
            def encode(self, input, **kwargs):
                seen_kwargs.update(kwargs)
                return np.array([[0.0] for _ in input])

        monkeypatch.setattr(server, "_load_model", lambda model_id: FakeModel())

        client = TestClient(server.app)
        response = client.post(
            "/v1/embeddings",
            json={
                "model": "BAAI/bge-m3",
                "input": ["search query"],
                "input_type": "query",
            },
        )
        assert response.status_code == 200
        assert "prompt_name" not in seen_kwargs
        assert seen_kwargs.get("normalize_embeddings") is True


class TestDeviceDetection:
    def test_get_device_env_cuda_falls_back_when_unavailable(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_DEVICE", "cuda")
        fake_torch = MagicMock()
        fake_torch.cuda.is_available.return_value = False
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        assert server._get_device() == "cpu"

    def test_get_device_env_cuda_when_available(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_DEVICE", "cuda")
        fake_torch = MagicMock()
        fake_torch.cuda.is_available.return_value = True
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        assert server._get_device() == "cuda"

    def test_get_device_env_mps_falls_back_when_unavailable(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_DEVICE", "mps")
        fake_torch = MagicMock()
        fake_torch.backends.mps.is_available.return_value = False
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        assert server._get_device() == "cpu"

    def test_get_device_defaults_to_cpu(self, monkeypatch):
        monkeypatch.delenv("EMBEDDING_DEVICE", raising=False)
        fake_torch = MagicMock()
        fake_torch.cuda.is_available.return_value = False
        fake_torch.backends.mps.is_available.return_value = False
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        assert server._get_device() == "cpu"


class TestWarmupEndpoint:
    def test_warmup_loads_first_installed_model(self, monkeypatch):
        """Warmup prefers first installed model in AVAILABLE_MODELS order."""
        loaded = []

        def fake_installed(model_id):
            return model_id == "Qwen/Qwen3-Embedding-0.6B"

        def fake_load(model_id):
            loaded.append(model_id)
            return object()

        monkeypatch.setattr(server, "_embedding_installed", fake_installed)
        monkeypatch.setattr(server, "_load_model", fake_load)
        client = TestClient(server.app)
        r = client.post("/v1/warmup")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["model"] == "Qwen/Qwen3-Embedding-0.6B"
        assert loaded == ["Qwen/Qwen3-Embedding-0.6B"]

    def test_warmup_prefers_bge_when_both_installed(self, monkeypatch):
        monkeypatch.setattr(server, "_embedding_installed", lambda mid: True)
        monkeypatch.setattr(server, "_load_model", lambda mid: object())
        client = TestClient(server.app)
        r = client.post("/v1/warmup")
        assert r.status_code == 200
        assert r.json()["model"] == "BAAI/bge-m3"

    def test_warmup_not_installed_returns_503(self, monkeypatch):
        monkeypatch.setattr(server, "_embedding_installed", lambda mid: False)
        client = TestClient(server.app)
        r = client.post("/v1/warmup")
        assert r.status_code == 503

    def test_warmup_load_failure_returns_500_with_detail(self, monkeypatch):
        """Warmup returns 500 with actual exception text when load fails."""
        monkeypatch.setattr(server, "_embedding_installed", lambda mid: True)

        def fake_load(model_id):
            raise RuntimeError("GPU out of memory")

        monkeypatch.setattr(server, "_load_model", fake_load)
        client = TestClient(server.app)
        r = client.post("/v1/warmup")
        assert r.status_code == 500
        detail = r.json()["detail"]
        assert "GPU out of memory" in detail
        assert "BAAI/bge-m3" in detail


class TestEmbeddingInstalled:
    def test_embedding_installed_false_for_empty_dir(self, monkeypatch, tmp_path: Path):
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        cache_dir = tmp_path / "models--BAAI--bge-m3"
        cache_dir.mkdir()
        assert server._embedding_installed("BAAI/bge-m3") is False

    def test_embedding_installed_false_when_dir_has_only_config(self, monkeypatch, tmp_path: Path):
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        cache_dir = tmp_path / "models--BAAI--bge-m3"
        cache_dir.mkdir()
        (cache_dir / "config.json").write_text("{}", encoding="utf-8")
        assert server._embedding_installed("BAAI/bge-m3") is False

    def test_embedding_installed_false_for_tiny_model_safetensors(
        self, monkeypatch, tmp_path: Path
    ):
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        cache_dir = tmp_path / "models--BAAI--bge-m3"
        nested = cache_dir / "snapshots" / "abc"
        nested.mkdir(parents=True)
        (nested / "config.json").write_text("{}", encoding="utf-8")
        (nested / "model.safetensors").write_bytes(b"weights")
        assert server._embedding_installed("BAAI/bge-m3") is False

    def test_embedding_installed_true_for_large_model_safetensors(
        self, monkeypatch, tmp_path: Path
    ):
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        cache_dir = tmp_path / "models--BAAI--bge-m3"
        nested = cache_dir / "snapshots" / "abc"
        nested.mkdir(parents=True)
        (nested / "config.json").write_text("{}", encoding="utf-8")
        (nested / "model.safetensors").write_bytes(b"x" * 1_000_001)
        assert server._embedding_installed("BAAI/bge-m3") is True

    def test_embedding_installed_false_for_large_weights_without_config(
        self, monkeypatch, tmp_path: Path
    ):
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        cache_dir = tmp_path / "models--BAAI--bge-m3"
        nested = cache_dir / "snapshots" / "abc"
        nested.mkdir(parents=True)
        (nested / "model.safetensors").write_bytes(b"x" * 1_000_001)
        assert server._embedding_installed("BAAI/bge-m3") is False

    def test_embedding_installed_false_for_tiny_pytorch_model_bin(
        self, monkeypatch, tmp_path: Path
    ):
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        cache_dir = tmp_path / "models--BAAI--bge-m3"
        nested = cache_dir / "snapshots" / "abc"
        nested.mkdir(parents=True)
        (nested / "config.json").write_text("{}", encoding="utf-8")
        (nested / "pytorch_model.bin").write_bytes(b"weights")
        assert server._embedding_installed("BAAI/bge-m3") is False

    def test_embedding_installed_true_for_large_pytorch_model_bin(
        self, monkeypatch, tmp_path: Path
    ):
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        cache_dir = tmp_path / "models--BAAI--bge-m3"
        nested = cache_dir / "snapshots" / "abc"
        nested.mkdir(parents=True)
        (nested / "config.json").write_text("{}", encoding="utf-8")
        (nested / "pytorch_model.bin").write_bytes(b"x" * 1_000_001)
        assert server._embedding_installed("BAAI/bge-m3") is True

    def test_embedding_installed_false_when_index_json_only(self, monkeypatch, tmp_path: Path):
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        cache_dir = tmp_path / "models--BAAI--bge-m3"
        nested = cache_dir / "snapshots" / "abc"
        nested.mkdir(parents=True)
        (nested / "config.json").write_text("{}", encoding="utf-8")
        (nested / "model.safetensors.index.json").write_text("{}", encoding="utf-8")
        assert server._embedding_installed("BAAI/bge-m3") is False

    def test_embedding_installed_true_when_index_and_large_shard(
        self, monkeypatch, tmp_path: Path
    ):
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        cache_dir = tmp_path / "models--BAAI--bge-m3"
        nested = cache_dir / "snapshots" / "abc"
        nested.mkdir(parents=True)
        (nested / "config.json").write_text("{}", encoding="utf-8")
        (nested / "model.safetensors.index.json").write_text("{}", encoding="utf-8")
        (nested / "model-00001-of-00002.safetensors").write_bytes(b"x" * 1_000_001)
        assert server._embedding_installed("BAAI/bge-m3") is True

    def test_embedding_installed_true_for_large_safetensors_fallback(
        self, monkeypatch, tmp_path: Path
    ):
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        cache_dir = tmp_path / "models--BAAI--bge-m3"
        nested = cache_dir / "snapshots" / "abc"
        nested.mkdir(parents=True)
        (nested / "config.json").write_text("{}", encoding="utf-8")
        # Named differently than model.safetensors but large enough for fallback.
        (nested / "model-00001-of-00002.safetensors").write_bytes(b"x" * 1_000_001)
        assert server._embedding_installed("BAAI/bge-m3") is True

    def test_embedding_installed_false_when_missing(self, monkeypatch, tmp_path: Path):
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        assert server._embedding_installed("BAAI/bge-m3") is False

    def test_embedding_installed_false_for_blobs_only_large_files(
        self, monkeypatch, tmp_path: Path
    ):
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        cache_dir = tmp_path / "models--BAAI--bge-m3"
        blobs = cache_dir / "blobs"
        blobs.mkdir(parents=True)
        (blobs / "largeblob").write_bytes(b"x" * 50_000_001)
        assert server._embedding_installed("BAAI/bge-m3") is False

    def test_embedding_installed_ignores_hf_home_outside_service_dir(
        self, monkeypatch, tmp_path: Path
    ):
        models_dir = tmp_path / "service" / "models"
        models_dir.mkdir(parents=True)
        outside = tmp_path / "outside_hf"
        snap = outside / "models--BAAI--bge-m3" / "snapshots" / "abc"
        snap.mkdir(parents=True)
        (snap / "config.json").write_text("{}", encoding="utf-8")
        (snap / "model.safetensors").write_bytes(b"x" * 1_000_001)

        monkeypatch.setattr(server, "SERVICE_DIR", tmp_path / "service")
        monkeypatch.setattr(server, "MODELS_DIR", models_dir)
        monkeypatch.setenv("HF_HOME", str(outside))
        assert server._embedding_installed("BAAI/bge-m3") is False

    def test_embedding_installed_uses_hf_home_under_service_dir(
        self, monkeypatch, tmp_path: Path
    ):
        service = tmp_path / "service"
        models_dir = service / "models"
        models_dir.mkdir(parents=True)
        hf_home = service / "alt_cache"
        snap = hf_home / "models--BAAI--bge-m3" / "snapshots" / "abc"
        snap.mkdir(parents=True)
        (snap / "config.json").write_text("{}", encoding="utf-8")
        (snap / "model.safetensors").write_bytes(b"x" * 1_000_001)

        monkeypatch.setattr(server, "SERVICE_DIR", service)
        monkeypatch.setattr(server, "MODELS_DIR", models_dir)
        monkeypatch.setenv("HF_HOME", str(hf_home))
        assert server._embedding_installed("BAAI/bge-m3") is True


class TestFindLocalModelPath:
    def test_find_local_model_path_prefers_snapshot_dir(self, monkeypatch, tmp_path: Path):
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        snap = tmp_path / "models--BAAI--bge-m3" / "snapshots" / "abc123"
        snap.mkdir(parents=True)
        (snap / "config.json").write_text("{}", encoding="utf-8")
        (snap / "pytorch_model.bin").write_bytes(b"x" * 1_000_001)
        found = server._find_local_model_path("BAAI/bge-m3")
        assert found == snap

    def test_find_local_model_path_weights_directly_under_models_dir(
        self, monkeypatch, tmp_path: Path
    ):
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        root = tmp_path / "models--BAAI--bge-m3"
        root.mkdir()
        (root / "config.json").write_text("{}", encoding="utf-8")
        (root / "model.safetensors").write_bytes(b"x" * 1_000_001)
        found = server._find_local_model_path("BAAI/bge-m3")
        assert found == root

    def test_find_local_model_path_sentence_transformers_prefix(
        self, monkeypatch, tmp_path: Path
    ):
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        snap = (
            tmp_path
            / "models--sentence-transformers--BAAI--bge-m3"
            / "snapshots"
            / "hash1"
        )
        snap.mkdir(parents=True)
        (snap / "config.json").write_text("{}", encoding="utf-8")
        (snap / "model.safetensors").write_bytes(b"x" * 1_000_001)
        found = server._find_local_model_path("BAAI/bge-m3")
        assert found == snap

    def test_find_local_model_path_none_for_tiny_or_incomplete(
        self, monkeypatch, tmp_path: Path
    ):
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        snap = tmp_path / "models--BAAI--bge-m3" / "snapshots" / "abc"
        snap.mkdir(parents=True)
        (snap / "config.json").write_text("{}", encoding="utf-8")
        (snap / "pytorch_model.bin").write_bytes(b"tiny")
        assert server._find_local_model_path("BAAI/bge-m3") is None

    def test_find_local_model_path_none_for_weights_without_config(
        self, monkeypatch, tmp_path: Path
    ):
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        snap = tmp_path / "models--BAAI--bge-m3" / "snapshots" / "abc"
        snap.mkdir(parents=True)
        (snap / "model.safetensors").write_bytes(b"x" * 1_000_001)
        assert server._find_local_model_path("BAAI/bge-m3") is None


class TestLoadModel:
    def test_load_model_prefers_local_files_only_when_installed(self, monkeypatch):
        """Installed cache loads from resolved local path with local_files_only=True."""
        calls = []
        local = Path("/fake/local/model")

        class FakeST:
            def __init__(self, model_id, device=None, cache_folder=None, local_files_only=False):
                calls.append(
                    {
                        "model_id": model_id,
                        "device": device,
                        "cache_folder": cache_folder,
                        "local_files_only": local_files_only,
                    }
                )

        fake_st_mod = MagicMock()
        fake_st_mod.SentenceTransformer = FakeST
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st_mod)
        monkeypatch.setattr(server, "_find_local_model_path", lambda mid: local)
        monkeypatch.setattr(server, "_get_device", lambda: "cpu")
        monkeypatch.setattr(server, "_embedding_model", None)
        monkeypatch.setattr(server, "_loaded_model_id", None)

        model = server._load_model("BAAI/bge-m3")
        assert model is not None
        assert len(calls) == 1
        assert calls[0]["local_files_only"] is True
        assert calls[0]["model_id"] == str(local)
        assert calls[0]["cache_folder"] is None

    def test_load_model_retries_without_local_on_local_failure(self, monkeypatch):
        """Local path load failure falls back to hub id with network allowed."""
        calls = []
        local = Path("/fake/local/model")

        class FakeST:
            def __init__(self, model_id, device=None, cache_folder=None, local_files_only=False):
                calls.append(
                    {
                        "model_id": model_id,
                        "local_files_only": local_files_only,
                        "cache_folder": cache_folder,
                    }
                )
                if local_files_only:
                    raise RuntimeError("missing weights")

        fake_st_mod = MagicMock()
        fake_st_mod.SentenceTransformer = FakeST
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st_mod)
        monkeypatch.setattr(server, "_find_local_model_path", lambda mid: local)
        monkeypatch.setattr(server, "_get_device", lambda: "cpu")
        monkeypatch.setattr(server, "_embedding_model", None)
        monkeypatch.setattr(server, "_loaded_model_id", None)

        model = server._load_model("BAAI/bge-m3")
        assert model is not None
        assert len(calls) == 2
        assert calls[0]["model_id"] == str(local)
        assert calls[0]["local_files_only"] is True
        assert calls[0]["cache_folder"] is None
        assert calls[1]["model_id"] == "BAAI/bge-m3"
        assert calls[1]["local_files_only"] is False
        assert calls[1]["cache_folder"] is not None

    def test_load_model_cuda_oom_retries_cpu(self, monkeypatch):
        """CUDA OOM on load retries once on cpu using local path."""
        calls = []
        local = Path("/fake/local/model")

        class FakeST:
            def __init__(self, model_id, device=None, cache_folder=None, local_files_only=False):
                calls.append({"device": device, "model_id": model_id})
                if device == "cuda":
                    raise RuntimeError("CUDA out of memory")

        fake_st_mod = MagicMock()
        fake_st_mod.SentenceTransformer = FakeST
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st_mod)
        monkeypatch.setattr(server, "_find_local_model_path", lambda mid: local)
        monkeypatch.setattr(server, "_get_device", lambda: "cuda")
        monkeypatch.setattr(server, "_embedding_model", None)
        monkeypatch.setattr(server, "_loaded_model_id", None)

        model = server._load_model("BAAI/bge-m3")
        assert model is not None
        assert [c["device"] for c in calls] == ["cuda", "cpu"]
        assert all(c["model_id"] == str(local) for c in calls)

    def test_load_model_uses_resolved_local_snapshot_path(self, monkeypatch, tmp_path: Path):
        """Real snapshot layout under MODELS_DIR is passed as model path without cache_folder."""
        calls = []
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        snap = tmp_path / "models--BAAI--bge-m3" / "snapshots" / "abc123"
        snap.mkdir(parents=True)
        (snap / "config.json").write_text("{}", encoding="utf-8")
        (snap / "pytorch_model.bin").write_bytes(b"x" * 1_000_001)

        class FakeST:
            def __init__(self, model_id, device=None, cache_folder=None, local_files_only=False):
                calls.append(
                    {
                        "model_id": model_id,
                        "device": device,
                        "cache_folder": cache_folder,
                        "local_files_only": local_files_only,
                    }
                )

        fake_st_mod = MagicMock()
        fake_st_mod.SentenceTransformer = FakeST
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st_mod)
        monkeypatch.setattr(server, "_get_device", lambda: "cpu")
        monkeypatch.setattr(server, "_embedding_model", None)
        monkeypatch.setattr(server, "_loaded_model_id", None)

        model = server._load_model("BAAI/bge-m3")
        assert model is not None
        assert len(calls) == 1
        assert calls[0]["model_id"] == str(snap)
        assert calls[0]["cache_folder"] is None
        assert calls[0]["local_files_only"] is True

    def test_load_model_complete_cache_failure_reports_real_error(self, monkeypatch, tmp_path: Path):
        """When the cache IS complete but load fails, don't blame 'cache incomplete'."""
        monkeypatch.setattr(server, "MODELS_DIR", tmp_path)
        snap = tmp_path / "models--BAAI--bge-m3" / "snapshots" / "abc123"
        snap.mkdir(parents=True)
        (snap / "config.json").write_text("{}", encoding="utf-8")
        (snap / "pytorch_model.bin").write_bytes(b"x" * 1_000_001)

        class FakeST:
            def __init__(self, *args, **kwargs):
                raise RuntimeError(
                    "we now require users to upgrade torch to at least v2.6"
                )

        fake_st_mod = MagicMock()
        fake_st_mod.SentenceTransformer = FakeST
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st_mod)
        monkeypatch.setattr(server, "_get_device", lambda: "cpu")
        monkeypatch.setattr(server, "_embedding_model", None)
        monkeypatch.setattr(server, "_loaded_model_id", None)

        try:
            server._load_model("BAAI/bge-m3")
        except RuntimeError as exc:
            msg = str(exc)
            assert "cache incomplete" not in msg
            assert "BAAI/bge-m3" in msg
            assert "at least v2.6" in msg  # real exception text preserved
        else:
            raise AssertionError("expected RuntimeError when load fails")

    def test_load_model_incomplete_cache_failure_keeps_redeploy_guidance(self, monkeypatch, tmp_path: Path):
        """When the cache IS incomplete, keep the re-deploy guidance."""
        local = tmp_path / "incomplete_model"
        local.mkdir()

        class FakeST:
            def __init__(self, *args, **kwargs):
                raise RuntimeError("missing weights")

        fake_st_mod = MagicMock()
        fake_st_mod.SentenceTransformer = FakeST
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st_mod)
        monkeypatch.setattr(server, "_find_local_model_path", lambda mid: local)
        monkeypatch.setattr(server, "_dir_is_complete_model", lambda p: False)
        monkeypatch.setattr(server, "_get_device", lambda: "cpu")
        monkeypatch.setattr(server, "_embedding_model", None)
        monkeypatch.setattr(server, "_loaded_model_id", None)

        try:
            server._load_model("BAAI/bge-m3")
        except RuntimeError as exc:
            msg = str(exc)
            assert "re-deploy" in msg
            assert "cache incomplete" in msg
        else:
            raise AssertionError("expected RuntimeError when load fails")
