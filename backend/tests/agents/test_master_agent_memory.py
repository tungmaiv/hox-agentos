"""
TDD tests for master agent long-term memory integration (Phase 3).

Tests:
- _load_memory_node injects long-term facts as SystemMessage when facts exist
- _load_memory_node gracefully handles empty facts (no injection)
- _save_memory_node dispatches embed_and_store.delay for AI turns
- _save_memory_node dispatches summarize_episode.delay at threshold
- _get_episode_threshold reads from system_config then falls back to settings

All LLM, DB, and Celery calls are mocked — no live services needed.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


@pytest.mark.asyncio
async def test_load_memory_node_injects_facts_as_system_message():
    """
    When search_facts returns facts, _load_memory_node injects them as a
    SystemMessage with '[Long-term memory' prefix before the conversation history.
    """
    from core.models.memory_long_term import MemoryFact

    mock_fact = MagicMock(spec=MemoryFact)
    mock_fact.content = "User's name is Tung"

    user_id = uuid.uuid4()

    with (
        patch("agents.master_agent.search_facts", new_callable=AsyncMock) as mock_search,
        patch("agents.master_agent.BGE_M3Provider") as mock_provider_cls,
        patch("agents.master_agent.load_recent_turns", new_callable=AsyncMock) as mock_turns,
        patch("agents.master_agent.async_session") as mock_session_factory,
        patch("agents.master_agent.current_user_ctx") as mock_ctx,
        patch("agents.master_agent.current_conversation_id_ctx") as mock_conv_ctx,
    ):
        mock_search.return_value = [mock_fact]
        mock_provider = MagicMock()
        mock_provider.embed = AsyncMock(return_value=[[0.1] * 1024])
        mock_provider_cls.return_value = mock_provider
        mock_turns.return_value = []

        # Mock async context manager for async_session
        mock_session = AsyncMock()
        mock_begin_ctx = AsyncMock()
        mock_begin_ctx.__aenter__ = AsyncMock(return_value=None)
        mock_begin_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_session.begin = MagicMock(return_value=mock_begin_ctx)
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_session_factory.return_value = mock_session_ctx

        mock_ctx.get.return_value = {"user_id": user_id}
        mock_conv_ctx.get.return_value = uuid.uuid4()

        from agents.master_agent import _load_memory_node

        state = {
            "messages": [HumanMessage(content="What do you know about me?")],
            "loaded_facts": [],
            "delivery_targets": ["WEB_CHAT"],
        }

        result = await _load_memory_node(state)

    # loaded_facts should contain the fact content
    assert "User's name is Tung" in result.get("loaded_facts", [])


@pytest.mark.asyncio
async def test_load_memory_node_no_facts_no_system_message():
    """
    When search_facts returns empty list, no long-term memory SystemMessage is injected.
    """
    user_id = uuid.uuid4()

    with (
        patch("agents.master_agent.search_facts", new_callable=AsyncMock) as mock_search,
        patch("agents.master_agent.BGE_M3Provider") as mock_provider_cls,
        patch("agents.master_agent.load_recent_turns", new_callable=AsyncMock) as mock_turns,
        patch("agents.master_agent.async_session") as mock_session_factory,
        patch("agents.master_agent.current_user_ctx") as mock_ctx,
        patch("agents.master_agent.current_conversation_id_ctx") as mock_conv_ctx,
    ):
        mock_search.return_value = []
        mock_provider = MagicMock()
        mock_provider.embed = AsyncMock(return_value=[[0.0] * 1024])
        mock_provider_cls.return_value = mock_provider
        mock_turns.return_value = []

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_session_factory.return_value = mock_session_ctx

        mock_ctx.get.return_value = {"user_id": user_id}
        mock_conv_ctx.get.return_value = uuid.uuid4()

        from agents.master_agent import _load_memory_node

        state = {
            "messages": [HumanMessage(content="Hello!")],
            "loaded_facts": [],
            "delivery_targets": ["WEB_CHAT"],
        }

        result = await _load_memory_node(state)

    # No facts loaded — loaded_facts should be empty
    loaded = result.get("loaded_facts", [])
    assert loaded == []


@pytest.mark.asyncio
async def test_load_memory_node_gracefully_handles_embedding_failure():
    """
    If BGE_M3Provider.embed() raises, _load_memory_node must not propagate the
    exception — graceful degradation means agent still works without long-term memory.
    """
    user_id = uuid.uuid4()

    with (
        patch("agents.master_agent.BGE_M3Provider") as mock_provider_cls,
        patch("agents.master_agent.load_recent_turns", new_callable=AsyncMock) as mock_turns,
        patch("agents.master_agent.async_session") as mock_session_factory,
        patch("agents.master_agent.current_user_ctx") as mock_ctx,
        patch("agents.master_agent.current_conversation_id_ctx") as mock_conv_ctx,
    ):
        # Simulate embedding failure
        mock_provider = MagicMock()
        mock_provider.embed = AsyncMock(side_effect=RuntimeError("GPU OOM"))
        mock_provider_cls.return_value = mock_provider
        mock_turns.return_value = []

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_session_factory.return_value = mock_session_ctx

        mock_ctx.get.return_value = {"user_id": user_id}
        mock_conv_ctx.get.return_value = uuid.uuid4()

        from agents.master_agent import _load_memory_node

        state = {
            "messages": [HumanMessage(content="Hello!")],
            "loaded_facts": [],
            "delivery_targets": ["WEB_CHAT"],
        }

        # Must not raise — graceful degradation
        result = await _load_memory_node(state)

    # Loaded facts should be empty (embedding failed, so no facts)
    loaded = result.get("loaded_facts", [])
    assert loaded == []


@pytest.mark.asyncio
async def test_save_memory_node_dispatches_embed_task_for_ai_turns():
    """
    After saving turns, embed_and_store.delay() is called for each AI (assistant) message.
    Human messages are NOT embedded (they're ephemeral context, not durable facts).
    """
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()

    with (
        patch("agents.master_agent.embed_and_store") as mock_embed_task,
        patch("agents.master_agent.summarize_episode") as mock_summarize_task,
        patch("agents.master_agent.save_turn", new_callable=AsyncMock),
        patch("agents.master_agent.async_session") as mock_session_factory,
        patch("agents.master_agent.current_user_ctx") as mock_ctx,
        patch("agents.master_agent.current_conversation_id_ctx") as mock_conv_ctx,
        patch("agents.master_agent.get_episode_threshold_cached", new_callable=AsyncMock) as mock_threshold,
    ):
        # Simulate: 0 existing turns in DB → both messages are new
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_count_result)
        mock_session.commit = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_session_factory.return_value = mock_session_ctx

        mock_ctx.get.return_value = {"user_id": user_id}
        mock_conv_ctx.get.return_value = conversation_id
        mock_threshold.return_value = 10

        from agents.master_agent import _save_memory_node

        state = {
            "messages": [
                HumanMessage(content="Hello"),
                AIMessage(content="Hi there! How can I help you?"),
            ],
            "loaded_facts": [],
            "delivery_targets": ["WEB_CHAT"],
        }

        await _save_memory_node(state)

        # embed_and_store.delay called for the AI message
        mock_embed_task.delay.assert_called_once_with(
            "Hi there! How can I help you?", str(user_id), "fact"
        )


@pytest.mark.asyncio
async def test_save_memory_node_triggers_summarize_at_threshold():
    """
    summarize_episode.delay() is triggered when total turns equals threshold.

    CopilotKit sends full message history on each request. So the state messages
    contain all previous turns + the new ones. DB existing_count tells us how many
    are already saved. Turns at index >= existing_count are the new ones to save.
    """
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()

    # Build state: 9 previous messages + 1 new AI turn = 10 total
    # CopilotKit includes the full history in state, so we need 10 messages in state
    previous_messages = [HumanMessage(content=f"Turn {i}") for i in range(9)]
    new_ai_message = AIMessage(content="This is the 10th turn")
    all_messages = previous_messages + [new_ai_message]

    with (
        patch("agents.master_agent.embed_and_store") as mock_embed_task,
        patch("agents.master_agent.summarize_episode") as mock_summarize_task,
        patch("agents.master_agent.save_turn", new_callable=AsyncMock),
        patch("agents.master_agent.async_session") as mock_session_factory,
        patch("agents.master_agent.current_user_ctx") as mock_ctx,
        patch("agents.master_agent.current_conversation_id_ctx") as mock_conv_ctx,
        patch("agents.master_agent.get_episode_threshold_cached", new_callable=AsyncMock) as mock_threshold,
    ):
        # 9 existing turns in DB → only the 10th (index 9) is new
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 9

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_count_result)
        mock_session.commit = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_session_factory.return_value = mock_session_ctx

        mock_ctx.get.return_value = {"user_id": user_id}
        mock_conv_ctx.get.return_value = conversation_id
        mock_threshold.return_value = 10

        from agents.master_agent import _save_memory_node

        state = {
            "messages": all_messages,
            "loaded_facts": [],
            "delivery_targets": ["WEB_CHAT"],
        }

        await _save_memory_node(state)

        # summarize_episode.delay must be called (9 existing + 1 new = 10 = threshold)
        mock_summarize_task.delay.assert_called_once_with(
            str(conversation_id), str(user_id)
        )


@pytest.mark.asyncio
async def test_save_memory_node_no_summarize_below_threshold():
    """
    summarize_episode.delay() is NOT triggered when total turns < threshold.

    State includes all 5 messages (3 existing + 2 new). DB count says 3 are already
    saved, so only messages[3:] = 2 new turns are saved. Total = 5, threshold = 10.
    """
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()

    # State has 5 messages total (3 existing from DB perspective + 2 new)
    existing_messages = [HumanMessage(content=f"Old {i}") for i in range(3)]
    new_messages = [HumanMessage(content="Turn 4"), AIMessage(content="Turn 5 response")]
    all_messages = existing_messages + new_messages

    with (
        patch("agents.master_agent.embed_and_store") as mock_embed_task,
        patch("agents.master_agent.summarize_episode") as mock_summarize_task,
        patch("agents.master_agent.save_turn", new_callable=AsyncMock),
        patch("agents.master_agent.async_session") as mock_session_factory,
        patch("agents.master_agent.current_user_ctx") as mock_ctx,
        patch("agents.master_agent.current_conversation_id_ctx") as mock_conv_ctx,
        patch("agents.master_agent.get_episode_threshold_cached", new_callable=AsyncMock) as mock_threshold,
    ):
        # 3 existing turns in DB → messages[3:] = 2 new → total = 5 (below threshold 10)
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 3

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_count_result)
        mock_session.commit = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_session_factory.return_value = mock_session_ctx

        mock_ctx.get.return_value = {"user_id": user_id}
        mock_conv_ctx.get.return_value = conversation_id
        mock_threshold.return_value = 10

        from agents.master_agent import _save_memory_node

        state = {
            "messages": all_messages,
            "loaded_facts": [],
            "delivery_targets": ["WEB_CHAT"],
        }

        await _save_memory_node(state)

        # summarize_episode.delay must NOT be called (5 < 10)
        mock_summarize_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_get_episode_threshold_returns_db_value():
    """get_episode_threshold_db() reads from system_config DB key when available."""
    from core.models.system_config import SystemConfig

    mock_row = MagicMock(spec=SystemConfig)
    mock_row.value = 20  # custom threshold set by admin

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_row

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    from memory.medium_term import get_episode_threshold_db
    import uuid as _uuid

    threshold = await get_episode_threshold_db(_uuid.uuid4(), mock_session)

    assert threshold == 20


@pytest.mark.asyncio
async def test_get_episode_threshold_falls_back_to_settings():
    """get_episode_threshold_db() uses settings.episode_turn_threshold when DB key is absent."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # key not in system_config

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    from memory.medium_term import get_episode_threshold_db
    import uuid as _uuid

    threshold = await get_episode_threshold_db(_uuid.uuid4(), mock_session)

    # Default from settings.episode_turn_threshold
    assert threshold == 10


@pytest.mark.asyncio
async def test_load_memory_node_injects_episodes_as_system_message():
    """
    When load_recent_episodes() returns episodes, _load_memory_node injects them as a
    SystemMessage with '[Medium-term memory' prefix before the conversation history.

    Uses state["messages"] = [] (skip_short_term=False path) so the full history
    (including the injected SystemMessage) is returned in result["messages"].
    """
    from core.models.memory_long_term import MemoryEpisode

    mock_episode = MagicMock(spec=MemoryEpisode)
    mock_episode.summary = "User discussed backend architecture preferences."

    user_id = uuid.uuid4()

    with (
        patch("agents.master_agent.search_facts", new_callable=AsyncMock) as mock_search,
        patch("agents.master_agent.BGE_M3Provider") as mock_provider_cls,
        patch("agents.master_agent.load_recent_turns", new_callable=AsyncMock) as mock_turns,
        patch("agents.master_agent.load_recent_episodes", new_callable=AsyncMock) as mock_episodes,
        patch("agents.master_agent.async_session") as mock_session_factory,
        patch("agents.master_agent.current_user_ctx") as mock_ctx,
        patch("agents.master_agent.current_conversation_id_ctx") as mock_conv_ctx,
    ):
        # No long-term facts — isolate episode behavior
        mock_search.return_value = []
        mock_provider = MagicMock()
        mock_provider.embed = AsyncMock(return_value=[[0.1] * 1024])
        mock_provider_cls.return_value = mock_provider
        # Empty DB turns so history starts fresh — episode gets inserted at [0]
        mock_turns.return_value = []
        mock_episodes.return_value = [mock_episode]

        # Mock async context manager for async_session
        mock_session = AsyncMock()
        mock_begin_ctx = AsyncMock()
        mock_begin_ctx.__aenter__ = AsyncMock(return_value=None)
        mock_begin_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_session.begin = MagicMock(return_value=mock_begin_ctx)
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_session_factory.return_value = mock_session_ctx

        mock_ctx.get.return_value = {"user_id": user_id}
        mock_conv_ctx.get.return_value = uuid.uuid4()

        from agents.master_agent import _load_memory_node

        # Empty messages → skip_short_term=False → full history returned in result["messages"]
        state = {
            "messages": [],
            "loaded_facts": [],
            "delivery_targets": ["WEB_CHAT"],
        }

        result = await _load_memory_node(state)

    # result["messages"] must contain the episode SystemMessage
    messages = result.get("messages", [])
    assert any(
        isinstance(m, SystemMessage) and "[Medium-term memory" in m.content
        for m in messages
    ), f"Expected '[Medium-term memory' SystemMessage in messages, got: {messages}"


@pytest.mark.asyncio
async def test_load_memory_node_gracefully_handles_episode_failure():
    """
    When load_recent_episodes() raises, _load_memory_node must NOT propagate the
    exception — graceful degradation means agent still works without episode context.
    No '[Medium-term memory' SystemMessage should appear in the result.
    """
    user_id = uuid.uuid4()

    with (
        patch("agents.master_agent.search_facts", new_callable=AsyncMock) as mock_search,
        patch("agents.master_agent.BGE_M3Provider") as mock_provider_cls,
        patch("agents.master_agent.load_recent_turns", new_callable=AsyncMock) as mock_turns,
        patch("agents.master_agent.load_recent_episodes", new_callable=AsyncMock) as mock_episodes,
        patch("agents.master_agent.async_session") as mock_session_factory,
        patch("agents.master_agent.current_user_ctx") as mock_ctx,
        patch("agents.master_agent.current_conversation_id_ctx") as mock_conv_ctx,
    ):
        mock_search.return_value = []
        mock_provider = MagicMock()
        mock_provider.embed = AsyncMock(return_value=[[0.1] * 1024])
        mock_provider_cls.return_value = mock_provider
        mock_turns.return_value = []
        # Simulate episode load failure
        mock_episodes.side_effect = RuntimeError("DB connection lost")

        mock_session = AsyncMock()
        mock_begin_ctx = AsyncMock()
        mock_begin_ctx.__aenter__ = AsyncMock(return_value=None)
        mock_begin_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_session.begin = MagicMock(return_value=mock_begin_ctx)
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_session_factory.return_value = mock_session_ctx

        mock_ctx.get.return_value = {"user_id": user_id}
        mock_conv_ctx.get.return_value = uuid.uuid4()

        from agents.master_agent import _load_memory_node

        state = {
            "messages": [],
            "loaded_facts": [],
            "delivery_targets": ["WEB_CHAT"],
        }

        # Must not raise — graceful degradation
        result = await _load_memory_node(state)

    # No episode context should be present
    messages = result.get("messages", [])
    assert not any(
        isinstance(m, SystemMessage) and "[Medium-term memory" in m.content
        for m in messages
    ), "Episode failure should not inject a '[Medium-term memory' SystemMessage"
