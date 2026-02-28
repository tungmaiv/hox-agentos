"""Tests for SkillExecutor -- procedural skill pipeline execution."""
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from skills.executor import SkillExecutor, SkillResult, SkillStepError


@dataclass
class FakeSkill:
    """Minimal skill-like object for testing."""

    name: str = "test_skill"
    procedure_json: dict[str, Any] | None = None


def _make_user_context() -> dict[str, Any]:
    return {
        "user_id": uuid4(),
        "email": "test@blitz.local",
        "username": "testuser",
        "roles": ["employee"],
        "groups": [],
    }


@pytest.fixture
def executor() -> SkillExecutor:
    return SkillExecutor()


@pytest.fixture
def user_context() -> dict[str, Any]:
    return _make_user_context()


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


class TestToolStep:
    @pytest.mark.asyncio
    async def test_tool_step_succeeds(
        self, executor: SkillExecutor, user_context: dict, mock_session: AsyncMock
    ) -> None:
        """Tool step with mocked tool registry and handler."""
        handler = AsyncMock(return_value="tool result data")
        skill = FakeSkill(
            procedure_json={
                "schema_version": "1.0",
                "steps": [
                    {
                        "id": "fetch",
                        "type": "tool",
                        "tool": "email.fetch",
                        "params": {"limit": "10"},
                    }
                ],
            }
        )

        with (
            patch("skills.executor.get_tool", new_callable=AsyncMock) as mock_get_tool,
            patch("skills.executor.check_tool_acl", new_callable=AsyncMock) as mock_acl,
        ):
            mock_get_tool.return_value = {
                "name": "email.fetch",
                "handler_module": "tools.email",
                "handler_function": "fetch_emails",
            }
            mock_acl.return_value = True

            with patch("importlib.import_module") as mock_import:
                mock_module = MagicMock()
                mock_module.fetch_emails = handler
                mock_import.return_value = mock_module

                result = await executor.run(skill, user_context, mock_session)

        assert result.success is True
        assert result.step_outputs["fetch"] == "tool result data"

    @pytest.mark.asyncio
    async def test_tool_step_acl_denied(
        self, executor: SkillExecutor, user_context: dict, mock_session: AsyncMock
    ) -> None:
        """Tool step denied by ACL returns failure."""
        skill = FakeSkill(
            procedure_json={
                "schema_version": "1.0",
                "steps": [
                    {"id": "admin_op", "type": "tool", "tool": "admin.delete"},
                ],
            }
        )

        with (
            patch("skills.executor.get_tool", new_callable=AsyncMock) as mock_get_tool,
            patch("skills.executor.check_tool_acl", new_callable=AsyncMock) as mock_acl,
        ):
            mock_get_tool.return_value = {
                "name": "admin.delete",
                "handler_module": "tools.admin",
                "handler_function": "delete_all",
            }
            mock_acl.return_value = False

            result = await executor.run(skill, user_context, mock_session)

        assert result.success is False
        assert result.failed_step == "admin_op"
        assert "Access denied" in result.output

    @pytest.mark.asyncio
    async def test_tool_not_found(
        self, executor: SkillExecutor, user_context: dict, mock_session: AsyncMock
    ) -> None:
        """Tool step with unknown tool returns failure."""
        skill = FakeSkill(
            procedure_json={
                "schema_version": "1.0",
                "steps": [
                    {"id": "s1", "type": "tool", "tool": "nonexistent.tool"},
                ],
            }
        )

        with patch("skills.executor.get_tool", new_callable=AsyncMock) as mock_get_tool:
            mock_get_tool.return_value = None

            result = await executor.run(skill, user_context, mock_session)

        assert result.success is False
        assert result.failed_step == "s1"
        assert "not found" in result.output


class TestLlmStep:
    @pytest.mark.asyncio
    async def test_llm_step_succeeds(
        self, executor: SkillExecutor, user_context: dict, mock_session: AsyncMock
    ) -> None:
        """LLM step invokes get_llm with correct alias."""
        skill = FakeSkill(
            procedure_json={
                "schema_version": "1.0",
                "steps": [
                    {
                        "id": "summarize",
                        "type": "llm",
                        "model_alias": "blitz/fast",
                        "prompt_template": "Summarize this text",
                    }
                ],
            }
        )

        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "Summary of text"
        mock_llm.ainvoke.return_value = mock_response

        with patch("skills.executor.get_llm") as mock_get_llm:
            mock_get_llm.return_value = mock_llm

            result = await executor.run(skill, user_context, mock_session)

        assert result.success is True
        assert result.step_outputs["summarize"] == "Summary of text"
        mock_get_llm.assert_called_once_with("blitz/fast")


class TestChainedSteps:
    @pytest.mark.asyncio
    async def test_tool_then_llm_with_variable_interpolation(
        self, executor: SkillExecutor, user_context: dict, mock_session: AsyncMock
    ) -> None:
        """Two chained steps: tool -> llm with {{step_id.output}} interpolation."""
        skill = FakeSkill(
            procedure_json={
                "schema_version": "1.0",
                "steps": [
                    {
                        "id": "fetch",
                        "type": "tool",
                        "tool": "email.fetch",
                        "params": {},
                    },
                    {
                        "id": "summarize",
                        "type": "llm",
                        "model_alias": "blitz/fast",
                        "prompt_template": "Summarize: {{fetch.output}}",
                    },
                ],
                "output": "{{summarize.output}}",
            }
        )

        handler = AsyncMock(return_value="3 new emails")
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "You have 3 emails"
        mock_llm.ainvoke.return_value = mock_response

        with (
            patch("skills.executor.get_tool", new_callable=AsyncMock) as mock_get_tool,
            patch("skills.executor.check_tool_acl", new_callable=AsyncMock) as mock_acl,
            patch("skills.executor.get_llm") as mock_get_llm,
        ):
            mock_get_tool.return_value = {
                "name": "email.fetch",
                "handler_module": "tools.email",
                "handler_function": "fetch_emails",
            }
            mock_acl.return_value = True
            mock_get_llm.return_value = mock_llm

            with patch("importlib.import_module") as mock_import:
                mock_module = MagicMock()
                mock_module.fetch_emails = handler
                mock_import.return_value = mock_module

                result = await executor.run(skill, user_context, mock_session)

        assert result.success is True
        assert result.step_outputs["fetch"] == "3 new emails"
        assert result.step_outputs["summarize"] == "You have 3 emails"
        assert result.output == "You have 3 emails"

        # Verify LLM received interpolated prompt
        mock_llm.ainvoke.assert_called_once_with("Summarize: 3 new emails")


class TestConditionStep:
    @pytest.mark.asyncio
    async def test_condition_uses_safe_eval(
        self, executor: SkillExecutor, user_context: dict, mock_session: AsyncMock
    ) -> None:
        """Condition step uses safe_eval_condition (no eval())."""
        handler = AsyncMock(return_value="data")
        skill = FakeSkill(
            procedure_json={
                "schema_version": "1.0",
                "steps": [
                    {"id": "check", "type": "tool", "tool": "status.check"},
                    {
                        "id": "decide",
                        "type": "condition",
                        "expression": "len(check) > 0",
                        "true_step": "notify",
                    },
                    {"id": "notify", "type": "tool", "tool": "email.send"},
                ],
            }
        )

        send_handler = AsyncMock(return_value="sent")

        with (
            patch("skills.executor.get_tool", new_callable=AsyncMock) as mock_get_tool,
            patch("skills.executor.check_tool_acl", new_callable=AsyncMock) as mock_acl,
            patch("skills.executor.safe_eval_condition") as mock_safe_eval,
        ):
            mock_get_tool.return_value = {
                "name": "status.check",
                "handler_module": "tools.status",
                "handler_function": "check_status",
            }
            mock_acl.return_value = True
            mock_safe_eval.return_value = True

            with patch("importlib.import_module") as mock_import:
                mock_module = MagicMock()
                mock_module.check_status = handler
                mock_module.send_email = send_handler
                mock_import.return_value = mock_module

                # Also mock get_tool for the second tool step
                mock_get_tool.side_effect = [
                    {
                        "name": "status.check",
                        "handler_module": "tools.status",
                        "handler_function": "check_status",
                    },
                    {
                        "name": "email.send",
                        "handler_module": "tools.email",
                        "handler_function": "send_email",
                    },
                ]

                result = await executor.run(skill, user_context, mock_session)

        assert result.success is True
        # Verify safe_eval was called (not eval)
        mock_safe_eval.assert_called_once()


class TestFailedStep:
    @pytest.mark.asyncio
    async def test_failed_step_returns_partial_result(
        self, executor: SkillExecutor, user_context: dict, mock_session: AsyncMock
    ) -> None:
        """Failed tool step stops execution and returns partial result."""
        handler_success = AsyncMock(return_value="step1 done")
        handler_fail = AsyncMock(side_effect=RuntimeError("Connection timeout"))

        skill = FakeSkill(
            procedure_json={
                "schema_version": "1.0",
                "steps": [
                    {"id": "s1", "type": "tool", "tool": "tool.a"},
                    {"id": "s2", "type": "tool", "tool": "tool.b"},
                    {"id": "s3", "type": "tool", "tool": "tool.c"},
                ],
            }
        )

        with (
            patch("skills.executor.get_tool", new_callable=AsyncMock) as mock_get_tool,
            patch("skills.executor.check_tool_acl", new_callable=AsyncMock) as mock_acl,
        ):
            mock_get_tool.return_value = {
                "name": "tool",
                "handler_module": "tools.test",
                "handler_function": "run",
            }
            mock_acl.return_value = True

            with patch("importlib.import_module") as mock_import:
                mock_module = MagicMock()
                # First call succeeds, second fails
                mock_module.run = AsyncMock(
                    side_effect=[handler_success.return_value, RuntimeError("Connection timeout")]
                )
                mock_import.return_value = mock_module

                result = await executor.run(skill, user_context, mock_session)

        assert result.success is False
        assert result.failed_step == "s2"
        assert "Connection timeout" in result.output
        # s1 completed, s2 failed, s3 not reached
        assert "s1" in result.step_outputs
        assert "s3" not in result.step_outputs


class TestEventEmitter:
    @pytest.mark.asyncio
    async def test_event_emitter_receives_progress(
        self, executor: SkillExecutor, user_context: dict, mock_session: AsyncMock
    ) -> None:
        """Event emitter callback receives step_progress events."""
        emitter = AsyncMock()
        skill = FakeSkill(
            procedure_json={
                "schema_version": "1.0",
                "steps": [
                    {
                        "id": "s1",
                        "type": "llm",
                        "model_alias": "blitz/fast",
                        "prompt_template": "Hello",
                        "description": "Say hello",
                    }
                ],
            }
        )

        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "Hi there"
        mock_llm.ainvoke.return_value = mock_response

        with patch("skills.executor.get_llm") as mock_get_llm:
            mock_get_llm.return_value = mock_llm

            result = await executor.run(
                skill, user_context, mock_session, event_emitter=emitter
            )

        assert result.success is True
        emitter.assert_called_once()
        event = emitter.call_args[0][0]
        assert event["type"] == "step_progress"
        assert event["skill_name"] == "test_skill"
        assert event["step_id"] == "s1"
        assert event["step_type"] == "llm"
        assert event["status"] == "completed"
        assert event["description"] == "Say hello"

    @pytest.mark.asyncio
    async def test_event_emitter_on_failure(
        self, executor: SkillExecutor, user_context: dict, mock_session: AsyncMock
    ) -> None:
        """Event emitter receives failed status on step error."""
        emitter = AsyncMock()
        skill = FakeSkill(
            procedure_json={
                "schema_version": "1.0",
                "steps": [
                    {"id": "s1", "type": "tool", "tool": "nonexistent"},
                ],
            }
        )

        with patch("skills.executor.get_tool", new_callable=AsyncMock) as mock_get_tool:
            mock_get_tool.return_value = None

            result = await executor.run(
                skill, user_context, mock_session, event_emitter=emitter
            )

        assert result.success is False
        emitter.assert_called_once()
        event = emitter.call_args[0][0]
        assert event["status"] == "failed"


class TestInvalidProcedure:
    @pytest.mark.asyncio
    async def test_missing_procedure_json(
        self, executor: SkillExecutor, user_context: dict, mock_session: AsyncMock
    ) -> None:
        """Skill with no procedure_json returns failure."""
        skill = FakeSkill(procedure_json=None)
        result = await executor.run(skill, user_context, mock_session)
        assert result.success is False
        assert "missing procedure_json" in result.output

    @pytest.mark.asyncio
    async def test_no_steps_key(
        self, executor: SkillExecutor, user_context: dict, mock_session: AsyncMock
    ) -> None:
        """Skill with procedure but no steps returns failure."""
        skill = FakeSkill(procedure_json={"schema_version": "1.0"})
        result = await executor.run(skill, user_context, mock_session)
        assert result.success is False
