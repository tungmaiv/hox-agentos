"""Tests for episode threshold and user instructions TTL caches."""
import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4


@pytest.mark.asyncio
async def test_episode_threshold_cached():
    """Episode threshold DB query is cached after first call."""
    user_id = uuid4()
    mock_session = AsyncMock()

    with patch("memory.medium_term.get_episode_threshold_db", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = 10

        from memory.medium_term import get_episode_threshold_cached, clear_threshold_cache
        clear_threshold_cache()

        result1 = await get_episode_threshold_cached(user_id, mock_session)
        result2 = await get_episode_threshold_cached(user_id, mock_session)

    assert result1 == 10
    assert result2 == 10
    mock_db.assert_called_once()


@pytest.mark.asyncio
async def test_user_instructions_cached():
    """User instructions DB query is cached after first call."""
    user_id = uuid4()
    mock_session = AsyncMock()

    with patch("api.routes.user_instructions.get_user_instructions_db", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = "Always respond in Vietnamese."

        from api.routes.user_instructions import get_user_instructions_cached, clear_instructions_cache
        clear_instructions_cache()

        result1 = await get_user_instructions_cached(user_id, mock_session)
        result2 = await get_user_instructions_cached(user_id, mock_session)

    assert result1 == "Always respond in Vietnamese."
    assert result2 == "Always respond in Vietnamese."
    mock_db.assert_called_once()
