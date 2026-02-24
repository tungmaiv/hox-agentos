"""
Tests for GET /health — no authentication required.

These are integration tests using FastAPI's TestClient.
The health endpoint must always return 200 regardless of auth state.
"""
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_returns_200() -> None:
    """Health check must return 200 OK with {status: ok}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_no_auth_required() -> None:
    """Health check must work without Authorization header."""
    response = client.get("/health", headers={})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_response_schema() -> None:
    """Response must match HealthResponse schema (only 'status' field)."""
    response = client.get("/health")
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"
