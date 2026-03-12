"""
Tests for SecurityScanClient and scan_skill_with_fallback.

TDD RED → GREEN cycle for Plan 24-05 Task 1.
Tests cover:
  - scan_skill() success returns scan_engine='docker'
  - TimeoutException triggers fallback (scan_engine='fallback')
  - ConnectError triggers fallback (scan_engine='fallback')
  - Fallback result has required fields
  - health_check() returns True on 200
  - health_check() returns False on any error
  - POST /api/admin/system/rescan-skills returns 202 (admin only)
  - scan_skill_with_fallback() calls in-process scanner and returns expected result
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SKILL_DATA: dict = {
    "name": "test_skill",
    "scripts": "import os\nprint('hello')",
    "requirements": "requests==2.28.0",
}

DOCKER_SCAN_RESPONSE: dict = {
    "score": 80,
    "recommendation": "approve",
    "findings": [],
    "bandit_issues": [],
    "pip_audit_issues": [],
    "secrets_found": False,
}


def _make_mock_http_client(post_return=None, post_side_effect=None, get_return=None, get_side_effect=None):
    """Build a mock httpx.AsyncClient context manager."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    if post_side_effect is not None:
        mock_client.post = AsyncMock(side_effect=post_side_effect)
    elif post_return is not None:
        mock_client.post = AsyncMock(return_value=post_return)
    if get_side_effect is not None:
        mock_client.get = AsyncMock(side_effect=get_side_effect)
    elif get_return is not None:
        mock_client.get = AsyncMock(return_value=get_return)
    return mock_client


def _make_http_response(status_code: int = 200, json_data: dict | None = None):
    """Build a mock httpx response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    if json_data is not None:
        mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ---------------------------------------------------------------------------
# SecurityScanClient.scan_skill() tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_skill_success():
    """scan_skill() returns dict with scan_engine='docker' on success."""
    from security.scan_client import SecurityScanClient

    mock_resp = _make_http_response(200, dict(DOCKER_SCAN_RESPONSE))
    mock_client = _make_mock_http_client(post_return=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        client = SecurityScanClient()
        result = await client.scan_skill(SKILL_DATA)

    assert result["scan_engine"] == "docker"
    assert result["score"] == 80
    assert result["recommendation"] == "approve"


@pytest.mark.asyncio
async def test_scan_skill_timeout_triggers_fallback():
    """scan_skill_with_fallback() catches TimeoutException, returns scan_engine='fallback'."""
    from security.scan_client import SecurityScanClient, scan_skill_with_fallback

    mock_fallback_report = MagicMock()
    mock_fallback_report.score = 60
    mock_fallback_report.recommendation = "review"
    mock_fallback_report.findings = []

    # Mock httpx to raise TimeoutException on POST
    mock_client = _make_mock_http_client(post_side_effect=httpx.TimeoutException("timeout"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch("skills.security_scanner.SecurityScanner.scan", new_callable=AsyncMock) as mock_scan:
            mock_scan.return_value = mock_fallback_report
            scan_client = SecurityScanClient()
            result = await scan_skill_with_fallback(SKILL_DATA, client=scan_client)

    assert result["scan_engine"] == "fallback"


@pytest.mark.asyncio
async def test_scan_skill_connect_error_triggers_fallback():
    """scan_skill_with_fallback() catches ConnectError, returns scan_engine='fallback'."""
    from security.scan_client import SecurityScanClient, scan_skill_with_fallback

    mock_fallback_report = MagicMock()
    mock_fallback_report.score = 55
    mock_fallback_report.recommendation = "review"
    mock_fallback_report.findings = []

    mock_client = _make_mock_http_client(post_side_effect=httpx.ConnectError("refused"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch("skills.security_scanner.SecurityScanner.scan", new_callable=AsyncMock) as mock_scan:
            mock_scan.return_value = mock_fallback_report
            scan_client = SecurityScanClient()
            result = await scan_skill_with_fallback(SKILL_DATA, client=scan_client)

    assert result["scan_engine"] == "fallback"


@pytest.mark.asyncio
async def test_fallback_result_has_required_fields():
    """Fallback result has all required keys: scan_engine, score, recommendation, findings."""
    from security.scan_client import SecurityScanClient, scan_skill_with_fallback

    mock_fallback_report = MagicMock()
    mock_fallback_report.score = 70
    mock_fallback_report.recommendation = "review"
    mock_fallback_report.findings = [{"tool": "bandit", "message": "test"}]

    mock_client = _make_mock_http_client(post_side_effect=httpx.ConnectError("refused"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch("skills.security_scanner.SecurityScanner.scan", new_callable=AsyncMock) as mock_scan:
            mock_scan.return_value = mock_fallback_report
            scan_client = SecurityScanClient()
            result = await scan_skill_with_fallback(SKILL_DATA, client=scan_client)

    assert "scan_engine" in result
    assert "score" in result
    assert "recommendation" in result
    assert "findings" in result


# ---------------------------------------------------------------------------
# SecurityScanClient.health_check() tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_check_returns_true_on_200():
    """health_check() returns True when /health returns 200."""
    from security.scan_client import SecurityScanClient

    mock_resp = _make_http_response(200)
    mock_client = _make_mock_http_client(get_return=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        client = SecurityScanClient()
        result = await client.health_check()

    assert result is True


@pytest.mark.asyncio
async def test_health_check_returns_false_on_error():
    """health_check() returns False on any exception (no exception propagation)."""
    from security.scan_client import SecurityScanClient

    mock_client = _make_mock_http_client(get_side_effect=httpx.ConnectError("refused"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        client = SecurityScanClient()
        result = await client.health_check()

    assert result is False


# ---------------------------------------------------------------------------
# POST /api/admin/system/rescan-skills endpoint test
# ---------------------------------------------------------------------------

@pytest.fixture
def sqlite_db():
    """Override get_db with an in-memory SQLite session for endpoint tests."""
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from core.db import Base, get_db
    from main import app

    import core.models.skill_definition  # noqa: F401 — registers in metadata

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_setup())

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    loop.run_until_complete(engine.dispose())
    loop.close()


def test_rescan_skills_endpoint_returns_202(sqlite_db: None):
    """POST /api/admin/system/rescan-skills returns 202 with status='accepted'."""
    from fastapi.testclient import TestClient

    from core.models.user import UserContext
    from main import app
    from security.deps import get_current_user

    def make_admin_ctx() -> UserContext:
        return UserContext(
            user_id=uuid4(),
            email="admin@blitz.local",
            username="admin_user",
            roles=["it-admin"],
            groups=["/it"],
        )

    app.dependency_overrides[get_current_user] = make_admin_ctx
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/admin/system/rescan-skills")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 202
    body = resp.json()
    assert "message" in body


# ---------------------------------------------------------------------------
# scan_skill_with_fallback integration test (replaces skill_handler on_create test)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_skill_with_fallback_calls_docker_first():
    """scan_skill_with_fallback() calls Docker scanner first when available."""
    from security.scan_client import scan_skill_with_fallback, SecurityScanClient

    scan_result = {
        "scan_engine": "docker",
        "score": 85,
        "recommendation": "approve",
        "findings": [],
        "bandit_issues": [],
        "pip_audit_issues": [],
        "secrets_found": False,
    }

    mock_client = AsyncMock(spec=SecurityScanClient)
    mock_client.scan_skill = AsyncMock(return_value=scan_result)

    result = await scan_skill_with_fallback(SKILL_DATA, client=mock_client)

    assert result["scan_engine"] == "docker"
    assert result["score"] == 85
    mock_client.scan_skill.assert_called_once_with(SKILL_DATA)
