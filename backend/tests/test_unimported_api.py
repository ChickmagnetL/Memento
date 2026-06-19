"""Tests for unimported-document scan and import endpoints."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api import documents
from main import app
from storage.sqlite_client import SQLiteClient


DRAFT_WITH_HEADER = """# 示例视频

- Platform: bilibili
- Video ID: bv1
- Source URL: https://www.bilibili.com/video/BV1xx

## Transcript

[00:01] 内容
"""


@pytest.fixture
async def client(tmp_path: Path, monkeypatch):
    sqlite = SQLiteClient(tmp_path / "metadata.db")
    await sqlite.connect()
    app.state.qdrant = SimpleNamespace(delete_for_document=lambda document_id: None)

    monkeypatch.setattr(
        documents,
        "get_settings",
        lambda: SimpleNamespace(storage=SimpleNamespace(data_dir=tmp_path)),
    )

    with TestClient(app) as test_client:
        # Override app.state after lifespan so endpoints use the temp DB.
        app.state.sqlite = sqlite
        yield test_client, sqlite
    await sqlite.close()


@pytest.mark.asyncio
async def test_list_unimported_excludes_already_imported(client, tmp_path: Path):
    test_client, sqlite = client
    knowledge = tmp_path / "knowledge" / "bilibili"
    knowledge.mkdir(parents=True)
    imported = knowledge / "bv1.md"
    unimported = knowledge / "bv2.md"
    imported.write_text(DRAFT_WITH_HEADER, encoding="utf-8")
    unimported.write_text(
        DRAFT_WITH_HEADER.replace("bv1", "bv2").replace("示例视频", "另一个"),
        encoding="utf-8",
    )
    await sqlite.create_document(
        document_id="d1", video_id=None, file_path=str(imported)
    )

    resp = test_client.get("/api/documents/unimported")

    assert resp.status_code == 200
    items = resp.json()
    assert [Path(i["file_path"]).name for i in items] == ["bv2.md"]
    assert items[0]["title"] == "另一个"
    assert items[0]["platform"] == "bilibili"


@pytest.mark.asyncio
async def test_list_unimported_empty_when_knowledge_dir_missing(client):
    test_client, _sqlite = client

    resp = test_client.get("/api/documents/unimported")

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_import_unimported_creates_document_records(client, tmp_path: Path):
    test_client, sqlite = client
    knowledge = tmp_path / "knowledge" / "bilibili"
    knowledge.mkdir(parents=True)
    target = knowledge / "bv1.md"
    target.write_text(DRAFT_WITH_HEADER, encoding="utf-8")

    resp = test_client.post(
        "/api/documents/unimported/import",
        json={"file_paths": [str(target)]},
    )

    assert resp.status_code == 201
    created = resp.json()
    assert len(created) == 1
    assert created[0]["file_path"] == str(target)
    assert created[0]["is_indexed"] is False
    assert created[0]["video_id"] is None
    # now imported, no longer shows as unimported
    assert test_client.get("/api/documents/unimported").json() == []


@pytest.mark.asyncio
async def test_import_unimported_skips_already_imported_and_missing(
    client, tmp_path: Path
):
    test_client, sqlite = client
    knowledge = tmp_path / "knowledge" / "bilibili"
    knowledge.mkdir(parents=True)
    target = knowledge / "bv1.md"
    target.write_text(DRAFT_WITH_HEADER, encoding="utf-8")
    await sqlite.create_document(
        document_id="d1", video_id=None, file_path=str(target)
    )

    resp = test_client.post(
        "/api/documents/unimported/import",
        json={"file_paths": [str(target), str(knowledge / "gone.md")]},
    )

    assert resp.status_code == 201
    assert resp.json() == []  # one already imported, one missing
