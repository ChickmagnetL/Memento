from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from api import embedding as embedding_api
from main import app
from schemas.embedding import (
    EmbeddingEnvironmentStatus,
    EmbeddingManagerProgress,
    EmbeddingManagerStatus,
    EmbeddingModelStatus,
)


def _manager():
    manager = MagicMock()
    manager.get_status.return_value = EmbeddingManagerStatus(
        environment=EmbeddingEnvironmentStatus(
            venv_exists=False,
            service_python_exists=False,
            service_dir_exists=True,
            platform="darwin",
            target_device="mps",
            runtime_device=None,
        ),
        models={
            "bge-m3": EmbeddingModelStatus(
                slug="bge-m3",
                label="BGE-M3",
                model_id="BAAI/bge-m3",
                installed=False,
            )
        },
        progress=EmbeddingManagerProgress(),
    )
    manager.install_model.return_value = EmbeddingManagerProgress(
        stage="queued", model_slug="bge-m3", percent=0
    )
    manager.uninstall_model.return_value = EmbeddingManagerProgress(
        stage="queued", model_slug="bge-m3", percent=0
    )
    manager.uninstall_all.return_value = EmbeddingManagerProgress(stage="queued")
    return manager


def test_embedding_local_status_reports_models_and_planned_device(monkeypatch):
    manager = _manager()
    monkeypatch.setattr(embedding_api, "_manager", manager)

    response = TestClient(app).get("/api/embedding/local/status")

    assert response.status_code == 200
    assert response.json()["environment"]["target_device"] == "mps"
    assert response.json()["models"]["bge-m3"]["installed"] is False


def test_embedding_local_install_and_uninstall_routes(monkeypatch):
    manager = _manager()
    monkeypatch.setattr(embedding_api, "_manager", manager)
    client = TestClient(app)

    install = client.post("/api/embedding/local/models/bge-m3/install")
    uninstall = client.delete("/api/embedding/local/models/bge-m3")
    uninstall_all = client.post("/api/embedding/local/uninstall-all")

    assert install.status_code == 202
    assert uninstall.status_code == 202
    assert uninstall_all.status_code == 202
    manager.install_model.assert_called_once_with("bge-m3")
    manager.uninstall_model.assert_called_once_with("bge-m3")
    manager.uninstall_all.assert_called_once_with()


def test_embedding_unknown_model_returns_404(monkeypatch):
    manager = _manager()
    manager.install_model.side_effect = KeyError("missing")
    monkeypatch.setattr(embedding_api, "_manager", manager)

    response = TestClient(app).post("/api/embedding/local/models/missing/install")

    assert response.status_code == 404
