# backend/tests/test_conversations.py
"""Tests for GET /api/conversations endpoint."""
import pytest
from fastapi.testclient import TestClient
from main import app


def test_conversations_list_requires_jwt():
    """GET /api/conversations returns 401 without Authorization header."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/conversations/")
    assert response.status_code == 401


def test_conversations_list_route_exists():
    """GET /api/conversations/ is registered (not 404)."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/conversations/")
    assert response.status_code != 404
