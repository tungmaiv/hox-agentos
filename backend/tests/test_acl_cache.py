"""Tests for Tool ACL TTL cache."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from security.acl import check_tool_acl_cached, clear_acl_cache


@pytest.mark.asyncio
async def test_acl_cache_avoids_second_db_query():
    """Second call for same (user_id, tool_name) uses cache — no second DB query."""
    user_id = uuid4()
    mock_session = AsyncMock()

    with patch("security.acl.check_tool_acl", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = True

        result1 = await check_tool_acl_cached(user_id, "email.fetch", mock_session)
        result2 = await check_tool_acl_cached(user_id, "email.fetch", mock_session)

    assert result1 is True
    assert result2 is True
    mock_check.assert_called_once()  # Only one DB query despite two calls


@pytest.mark.asyncio
async def test_acl_cache_different_users_not_shared():
    """Cache entries for different user_ids are independent."""
    user1 = uuid4()
    user2 = uuid4()
    mock_session = AsyncMock()

    with patch("security.acl.check_tool_acl", new_callable=AsyncMock) as mock_check:
        mock_check.side_effect = [True, False]

        result1 = await check_tool_acl_cached(user1, "email.fetch", mock_session)
        result2 = await check_tool_acl_cached(user2, "email.fetch", mock_session)

    assert result1 is True
    assert result2 is False
    assert mock_check.call_count == 2


def test_clear_acl_cache_empties_cache():
    """clear_acl_cache() empties the TTL cache (used in tests to reset state)."""
    from security.acl import _acl_cache
    _acl_cache[(uuid4(), "test.tool")] = True
    clear_acl_cache()
    assert len(_acl_cache) == 0
