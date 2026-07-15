from pathlib import Path
from types import SimpleNamespace

from core.rag import embedding_supervisor


def test_local_memento_embedding_endpoint_starts_service(monkeypatch, tmp_path):
    uvicorn = tmp_path / "uvicorn"
    uvicorn.touch()
    spawned = []
    health = iter([False, False, True])
    proc = SimpleNamespace(poll=lambda: None)

    monkeypatch.setattr(embedding_supervisor, "_spawned_proc", None)
    embedding_supervisor.ensure_embedding_running(
        "http://localhost:8003/v1",
        timeout=1,
        poll_interval=0,
        is_healthy=lambda endpoint: next(health),
        venv_path=lambda: uvicorn,
        spawn=lambda path, port: spawned.append((path, port)) or proc,
        sleep=lambda _: None,
    )

    assert spawned == [(uvicorn, 8003)]


def test_ollama_and_remote_embedding_endpoints_do_not_start_service(monkeypatch):
    spawned = []

    for endpoint in (
        "http://localhost:11434/v1",
        "https://example.com/v1",
    ):
        embedding_supervisor.ensure_embedding_running(
            endpoint,
            is_healthy=lambda _: False,
            spawn=lambda path, port: spawned.append((path, port)),
        )

    assert spawned == []
