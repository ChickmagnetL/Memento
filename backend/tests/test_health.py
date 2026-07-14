"""Tests for the health check endpoint."""

from fastapi.testclient import TestClient

from main import app

# NOTE: TestClient is NOT used as a context manager here, so the lifespan
# (DB init) does not run — /api/health needs no DB, keeping the test fast
# and free of side effects (no ~/memento_data created).
client = TestClient(app)


def test_health_returns_ok():
    """Health check endpoint should return 200 with status ok."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "memento-backend"


def test_api_docs_are_available():
    """Swagger UI should be available for Phase 1 API inspection."""
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "swagger-ui" in resp.text


def test_packaged_frontend_origin_is_allowed():
    resp = client.options(
        "/api/health",
        headers={
            "Origin": "http://127.0.0.1:3123",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://127.0.0.1:3123"
