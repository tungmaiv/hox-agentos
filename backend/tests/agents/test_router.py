"""TDD tests for intent classifier."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_classify_intent_email() -> None:
    with patch("agents.subagents.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="email"))
        mock_get_llm.return_value = mock_llm
        from agents.subagents.router import classify_intent

        result = await classify_intent("check my unread emails")
        assert result == "email"


@pytest.mark.asyncio
async def test_classify_intent_calendar() -> None:
    with patch("agents.subagents.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="calendar"))
        mock_get_llm.return_value = mock_llm
        from agents.subagents.router import classify_intent

        result = await classify_intent("what meetings do I have today?")
        assert result == "calendar"


@pytest.mark.asyncio
async def test_classify_intent_project() -> None:
    with patch("agents.subagents.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="project"))
        mock_get_llm.return_value = mock_llm
        from agents.subagents.router import classify_intent

        result = await classify_intent("what's the status of Project Alpha?")
        assert result == "project"


@pytest.mark.asyncio
async def test_classify_intent_general() -> None:
    with patch("agents.subagents.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="general"))
        mock_get_llm.return_value = mock_llm
        from agents.subagents.router import classify_intent

        result = await classify_intent("write me a haiku")
        assert result == "general"


@pytest.mark.asyncio
async def test_classify_intent_invalid_label_returns_general() -> None:
    """LLM returns garbage → 'general' (no exception)."""
    with patch("agents.subagents.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="INVALID_LABEL_XYZ"))
        mock_get_llm.return_value = mock_llm
        from agents.subagents.router import classify_intent

        result = await classify_intent("something")
        assert result == "general"


@pytest.mark.asyncio
async def test_classify_intent_llm_exception_returns_general() -> None:
    """LLM raises an exception → 'general' (no exception propagated)."""
    with patch("agents.subagents.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM connection failed"))
        mock_get_llm.return_value = mock_llm
        from agents.subagents.router import classify_intent

        result = await classify_intent("something")
        assert result == "general"
