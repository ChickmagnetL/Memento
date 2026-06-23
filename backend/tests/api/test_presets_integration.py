"""Integration tests for preset CRUD workflow."""

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def test_db(tmp_path: Path, monkeypatch):
    """Create a temporary test database."""
    db_file = tmp_path / "test_memento.db"
    monkeypatch.setattr("api.settings.db_path", lambda: db_file)

    # Initialize schema
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS model_presets (
            id TEXT PRIMARY KEY,
            model_name TEXT NOT NULL,
            name TEXT NOT NULL,
            config TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(model_name, name)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS active_preset (
            model_name TEXT PRIMARY KEY,
            preset_id TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (preset_id) REFERENCES model_presets(id) ON DELETE SET NULL
        )
        """
    )
    conn.commit()
    conn.close()

    return db_file


@pytest.fixture
def client(test_db):
    """Create test client."""
    return TestClient(app)


def test_complete_preset_workflow(client):
    """Test complete preset CRUD workflow with activation."""
    model_name = "chat"

    # 1. Initially no active preset
    response = client.get(f"/api/settings/models/{model_name}/active")
    assert response.status_code == 200
    assert response.json()["preset_id"] is None

    # 2. Create first preset with auto name
    response = client.post(
        f"/api/settings/models/{model_name}/presets",
        json={
            "config": {
                "provider": "cloud",
                "model": "claude-3-5-sonnet-20241022",
                "api_key": "sk-secret1",
            }
        },
    )
    assert response.status_code == 201
    preset1 = response.json()
    assert preset1["name"] == "预设1"
    assert preset1["config"]["api_key"] == "sk-s***"
    preset1_id = preset1["id"]

    # 3. Create second preset
    response = client.post(
        f"/api/settings/models/{model_name}/presets",
        json={
            "name": "Ollama本地",
            "config": {
                "provider": "ollama",
                "model": "llama3",
                "endpoint": "http://localhost:11434",
            },
        },
    )
    assert response.status_code == 201
    preset2 = response.json()
    assert preset2["name"] == "Ollama本地"
    preset2_id = preset2["id"]

    # 4. List presets (newest first)
    response = client.get(f"/api/settings/models/{model_name}/presets")
    assert response.status_code == 200
    presets = response.json()
    assert len(presets) == 2
    assert presets[0]["id"] == preset2_id
    assert presets[1]["id"] == preset1_id

    # 5. Activate first preset
    response = client.put(
        f"/api/settings/models/{model_name}/active",
        json={"preset_id": preset1_id},
    )
    assert response.status_code == 200

    # 6. Verify active preset
    response = client.get(f"/api/settings/models/{model_name}/active")
    assert response.status_code == 200
    data = response.json()
    assert data["preset_id"] == preset1_id
    assert data["preset"]["name"] == "预设1"

    # 7. Update preset name and config
    response = client.patch(
        f"/api/settings/models/{model_name}/presets/{preset1_id}",
        json={
            "name": "Claude官方",
            "config": {
                "provider": "cloud",
                "model": "claude-3-5-sonnet-20241022",
                "api_key": "sk-s***",  # Masked - should preserve original
            },
        },
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Claude官方"

    # 8. Delete active preset (should fallback to second preset)
    response = client.delete(f"/api/settings/models/{model_name}/presets/{preset1_id}")
    assert response.status_code == 204

    # 9. Verify fallback to second preset
    response = client.get(f"/api/settings/models/{model_name}/active")
    assert response.status_code == 200
    data = response.json()
    assert data["preset_id"] == preset2_id
    assert data["preset"]["name"] == "Ollama本地"

    # 10. Try to delete last preset (should be rejected with 400)
    response = client.delete(f"/api/settings/models/{model_name}/presets/{preset2_id}")
    assert response.status_code == 400
    assert "Cannot delete the last preset" in response.json()["detail"]

    # 11. Verify preset still exists
    response = client.get(f"/api/settings/models/{model_name}/active")
    assert response.status_code == 200
    assert response.json()["preset_id"] == preset2_id

    # 12. Verify preset is still in list
    response = client.get(f"/api/settings/models/{model_name}/presets")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_auto_name_skips_gaps(client):
    """Test that auto naming increments from max, not filling gaps."""
    model_name = "embedding"

    # Create preset 1
    resp1 = client.post(
        f"/api/settings/models/{model_name}/presets",
        json={"config": {"provider": "cloud", "model": "test"}},
    )
    preset1_id = resp1.json()["id"]
    assert resp1.json()["name"] == "预设1"

    # Create preset 2 and 3
    resp2 = client.post(
        f"/api/settings/models/{model_name}/presets",
        json={"config": {"provider": "cloud", "model": "test"}},
    )
    resp3 = client.post(
        f"/api/settings/models/{model_name}/presets",
        json={"config": {"provider": "cloud", "model": "test"}},
    )
    assert resp2.json()["name"] == "预设2"
    assert resp3.json()["name"] == "预设3"
    preset3_id = resp3.json()["id"]

    # Delete preset 2 (creates gap)
    resp2_id = resp2.json()["id"]
    client.delete(f"/api/settings/models/{model_name}/presets/{resp2_id}")

    # Create new preset - should be 预设4, not 预设2
    resp4 = client.post(
        f"/api/settings/models/{model_name}/presets",
        json={"config": {"provider": "cloud", "model": "test"}},
    )
    assert resp4.json()["name"] == "预设4"


def test_cross_model_isolation(client):
    """Test that presets are isolated per model."""
    # Create chat preset
    chat_resp = client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"provider": "cloud", "model": "claude"}},
    )
    chat_id = chat_resp.json()["id"]

    # Create embedding preset
    emb_resp = client.post(
        "/api/settings/models/embedding/presets",
        json={"config": {"provider": "openai", "model": "text-embedding-3-small"}},
    )
    emb_id = emb_resp.json()["id"]

    # Both should have same auto name (isolated counters)
    assert chat_resp.json()["name"] == "预设1"
    assert emb_resp.json()["name"] == "预设1"

    # Can't access chat preset via embedding endpoint
    response = client.get(f"/api/settings/models/embedding/presets/{chat_id}")
    assert response.status_code == 404

    # Can't access embedding preset via chat endpoint
    response = client.get(f"/api/settings/models/chat/presets/{emb_id}")
    assert response.status_code == 404
