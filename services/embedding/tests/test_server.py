"""Tests for the standalone embedding service."""
import sys
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
            def encode(self, input, normalize_embeddings):
                return np.array([[0.1, 0.2, 0.3] for _ in input])

        monkeypatch.setattr(server, "_load_model", lambda model_id: FakeModel())

        client = TestClient(server.app)
        response = client.post(
            "/v1/embeddings",
            json={"model": "all-MiniLM-L6-v2", "input": ["hello", "world"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        assert len(body["data"]) == 2
        assert body["data"][0]["index"] == 0
        assert body["data"][0]["embedding"] == [0.1, 0.2, 0.3]
        assert body["data"][1]["index"] == 1
        assert body["data"][1]["embedding"] == [0.1, 0.2, 0.3]
        assert body["model"] == "all-MiniLM-L6-v2"

    def test_embeddings_uses_requested_model(self, monkeypatch):
        """POST /v1/embeddings passes the model name to _load_model."""
        seen_model = None

        class FakeModel:
            def encode(self, input, normalize_embeddings):
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
            def encode(self, input, normalize_embeddings):
                return np.array([[0.0] for _ in input])

        def fake_load_model(model_id):
            nonlocal seen_model
            seen_model = model_id
            return FakeModel()

        monkeypatch.setattr(server, "_load_model", fake_load_model)

        client = TestClient(server.app)
        response = client.post("/v1/embeddings", json={"input": ["test"]})
        assert response.status_code == 200
        assert seen_model == server.DEFAULT_EMBEDDING_MODEL

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
            def encode(self, input, normalize_embeddings):
                raise RuntimeError("CUDA error")

        monkeypatch.setattr(server, "_load_model", lambda model_id: FakeModel())

        client = TestClient(server.app)
        response = client.post(
            "/v1/embeddings",
            json={"model": "all-MiniLM-L6-v2", "input": ["test"]},
        )
        assert response.status_code == 500
        detail = response.json()["detail"]
        assert "Embedding inference failed" in detail


class TestDeviceDetection:
    def test_get_device_reads_env_var(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_DEVICE", "cuda")
        assert server._get_device() == "cuda"

    def test_get_device_defaults_to_cpu(self, monkeypatch):
        monkeypatch.delenv("EMBEDDING_DEVICE", raising=False)
        fake_torch = MagicMock()
        fake_torch.cuda.is_available.return_value = False
        fake_torch.backends.mps.is_available.return_value = False
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        assert server._get_device() == "cpu"