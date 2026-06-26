"""Tests for preset CRUD API."""

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.settings import db_path
from main import app


@pytest.fixture
def test_db(tmp_path: Path, monkeypatch):
    """Create a temporary test database."""
    db_file = tmp_path / "test_memento.db"

    # Monkeypatch db_path to return test database
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


def test_create_preset_with_auto_name(client):
    """Test creating a preset with auto-generated name."""
    response = client.post(
        "/api/settings/models/chat/presets",
        json={
            "config": {
                "provider": "cloud",
                "model": "claude-3-5-sonnet-20241022",
                "api_key": "sk-test123",
            }
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Preset 1"
    assert data["model_name"] == "chat"
    assert data["config"]["provider"] == "cloud"
    assert data["config"]["api_key"] == "sk-t***"  # masked


def test_create_preset_with_custom_name(client):
    """Test creating a preset with custom name."""
    response = client.post(
        "/api/settings/models/embedding/presets",
        json={
            "name": "我的预设",
            "config": {
                "provider": "openai",
                "model": "text-embedding-3-small",
                "api_key": "sk-abc456",
            },
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "我的预设"
    assert data["config"]["api_key"] == "sk-a***"


def test_auto_name_increments(client):
    """Test that auto-generated names increment correctly."""
    # Create first preset
    client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"provider": "cloud", "model": "test1"}},
    )
    # Create second preset
    response = client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"provider": "cloud", "model": "test2"}},
    )
    assert response.json()["name"] == "Preset 2"


def test_list_presets(client):
    """Test listing presets."""
    # Create two presets
    client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"provider": "cloud", "model": "test1"}},
    )
    client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"provider": "ollama", "model": "test2"}},
    )

    response = client.get("/api/settings/models/chat/presets")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Newest first
    assert data[0]["name"] == "Preset 2"
    assert data[1]["name"] == "Preset 1"


def test_get_preset(client):
    """Test getting a specific preset."""
    # Create preset
    create_response = client.post(
        "/api/settings/models/chat/presets",
        json={"name": "测试", "config": {"provider": "cloud", "model": "test"}},
    )
    preset_id = create_response.json()["id"]

    # Get preset
    response = client.get(f"/api/settings/models/chat/presets/{preset_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "测试"
    assert data["id"] == preset_id


def test_get_preset_wrong_model(client):
    """Test getting a preset with wrong model_name returns 404."""
    # Create chat preset
    create_response = client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"provider": "cloud", "model": "test"}},
    )
    preset_id = create_response.json()["id"]

    # Try to get it as embedding preset
    response = client.get(f"/api/settings/models/embedding/presets/{preset_id}")
    assert response.status_code == 404


def test_update_preset(client):
    """Test updating a preset."""
    # Create preset
    create_response = client.post(
        "/api/settings/models/chat/presets",
        json={
            "name": "原始",
            "config": {"provider": "cloud", "model": "test", "api_key": "sk-old"},
        },
    )
    preset_id = create_response.json()["id"]

    # Update name and config
    response = client.patch(
        f"/api/settings/models/chat/presets/{preset_id}",
        json={
            "name": "更新后",
            "config": {"provider": "ollama", "model": "llama3", "endpoint": "http://localhost:11434"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "更新后"
    assert data["config"]["provider"] == "ollama"
    assert data["config"]["model"] == "llama3"


def test_update_preset_masked_key_preserved(client):
    """Test that masked API keys are preserved during update."""
    # Create preset with API key
    create_response = client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"provider": "cloud", "model": "test", "api_key": "sk-secret123"}},
    )
    preset_id = create_response.json()["id"]

    # Update with masked key (should preserve original)
    response = client.patch(
        f"/api/settings/models/chat/presets/{preset_id}",
        json={"config": {"provider": "cloud", "model": "updated", "api_key": "sk-s***"}},
    )
    assert response.status_code == 200

    # Verify key was preserved (still masked in response)
    data = response.json()
    assert data["config"]["api_key"] == "sk-s***"


def test_delete_preset(client):
    """Test deleting a preset."""
    # Create two presets (need at least two to delete one)
    client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"provider": "cloud", "model": "test1"}},
    )
    create_response = client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"provider": "cloud", "model": "test2"}},
    )
    preset_id = create_response.json()["id"]

    # Delete preset
    response = client.delete(f"/api/settings/models/chat/presets/{preset_id}")
    assert response.status_code == 204

    # Verify it's gone
    get_response = client.get(f"/api/settings/models/chat/presets/{preset_id}")
    assert get_response.status_code == 404


def test_delete_active_preset_fallback(client):
    """Test that deleting active preset falls back to first remaining."""
    # Create two presets
    resp1 = client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"provider": "cloud", "model": "test1"}},
    )
    preset1_id = resp1.json()["id"]

    resp2 = client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"provider": "cloud", "model": "test2"}},
    )
    preset2_id = resp2.json()["id"]

    # Set first preset as active
    client.put(
        "/api/settings/models/chat/active",
        json={"preset_id": preset1_id},
    )

    # Delete active preset
    client.delete(f"/api/settings/models/chat/presets/{preset1_id}")

    # Verify fallback to second preset (first in list after deletion)
    response = client.get("/api/settings/models/chat/active")
    assert response.status_code == 200
    data = response.json()
    assert data["preset_id"] == preset2_id


def test_set_active_preset(client):
    """Test setting active preset."""
    # Create preset
    create_response = client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"provider": "cloud", "model": "test"}},
    )
    preset_id = create_response.json()["id"]

    # Set as active
    response = client.put(
        "/api/settings/models/chat/active",
        json={"preset_id": preset_id},
    )
    assert response.status_code == 200
    assert response.json()["preset_id"] == preset_id


def test_get_active_preset(client):
    """Test getting active preset."""
    # Create and activate preset
    create_response = client.post(
        "/api/settings/models/chat/presets",
        json={"name": "活动预设", "config": {"provider": "cloud", "model": "test"}},
    )
    preset_id = create_response.json()["id"]
    client.put(
        "/api/settings/models/chat/active",
        json={"preset_id": preset_id},
    )

    # Get active preset
    response = client.get("/api/settings/models/chat/active")
    assert response.status_code == 200
    data = response.json()
    assert data["preset_id"] == preset_id
    assert data["preset"]["name"] == "活动预设"


def test_get_active_preset_none(client):
    """Test getting active preset when none is set."""
    response = client.get("/api/settings/models/chat/active")
    assert response.status_code == 200
    assert response.json()["preset_id"] is None
