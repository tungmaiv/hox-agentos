# backend/tests/test_credentials_api.py
"""Basic security gate tests for credential API endpoints."""
import pytest
from fastapi.testclient import TestClient
from main import app


def test_list_credentials_requires_jwt():
    """GET /api/credentials/ returns 401 without Authorization header."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/credentials/")
    assert response.status_code == 401


def test_list_credentials_route_exists():
    """GET /api/credentials/ is registered (not 404)."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/credentials/")
    assert response.status_code != 404


def test_delete_credential_requires_jwt():
    """DELETE /api/credentials/google returns 401 without Authorization header."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.delete("/api/credentials/google")
    assert response.status_code == 401


def test_delete_credential_route_exists():
    """DELETE /api/credentials/google is registered (not 404)."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.delete("/api/credentials/google")
    assert response.status_code != 404
