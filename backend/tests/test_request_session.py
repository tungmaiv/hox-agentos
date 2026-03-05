"""Tests for single-session-per-request via contextvar."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.db import get_session, _request_session_ctx
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_get_session_returns_contextvar_session():
    """get_session() returns the contextvar session when set."""
    mock_session = MagicMock(spec=AsyncSession)
    token = _request_session_ctx.set(mock_session)
    try:
        async with get_session() as session:
            assert session is mock_session
    finally:
        _request_session_ctx.reset(token)


@pytest.mark.asyncio
async def test_get_session_opens_new_when_not_set():
    """get_session() opens a new session when contextvar is None."""
    # Ensure no contextvar is set
    token = _request_session_ctx.set(None)
    try:
        with patch("core.db.async_session") as mock_factory:
            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=MagicMock(spec=AsyncSession))
            mock_cm.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = mock_cm

            async with get_session():
                pass

        mock_factory.assert_called_once()
    finally:
        _request_session_ctx.reset(token)
