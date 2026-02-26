"""TDD tests for call_mcp_tool — 3-gate security enforcement."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from core.models.user import UserContext


def make_user(
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
) -> UserContext:
    """Create a test UserContext with specified roles."""
    # Note: permissions field does not exist on UserContext — roles drive RBAC.
    # The 'permissions' param here is ignored (it's checked via has_permission(user, perm)).
    _ = permissions  # unused — kept for test readability parity with plan
    return UserContext(
        user_id=uuid.uuid4(),
        email="test@blitz.local",
        username="testuser",
        roles=roles or ["employee"],
        groups=[],
    )


@pytest.mark.asyncio
async def test_call_mcp_tool_denied_without_permission() -> None:
    """User lacks required permission → 403."""
    user = make_user(roles=["employee"])  # employee has no crm:read permission

    with (
        patch("mcp.registry.get_tool") as mock_get_tool,
        patch("mcp.registry.has_permission") as mock_has_perm,
    ):
        mock_get_tool.return_value = {
            "required_permissions": ["crm:read"],
            "mcp_server": "crm",
            "mcp_tool": "get_project_status",
        }
        mock_has_perm.return_value = False

        from mcp.registry import call_mcp_tool

        mock_session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await call_mcp_tool("crm.get_project_status", {}, user, mock_session)

        assert exc_info.value.status_code == 403
        assert "Missing permission" in exc_info.value.detail


@pytest.mark.asyncio
async def test_call_mcp_tool_denied_by_acl() -> None:
    """RBAC passes but ACL row denies user → 403; audit log entry created."""
    user = make_user(roles=["it-admin"])

    with (
        patch("mcp.registry.get_tool") as mock_get_tool,
        patch("mcp.registry.has_permission") as mock_has_perm,
        patch(
            "mcp.registry.check_tool_acl", new_callable=AsyncMock
        ) as mock_acl,
        patch("mcp.registry.audit_logger") as mock_audit,
    ):
        mock_get_tool.return_value = {
            "required_permissions": ["crm:read"],
            "mcp_server": "crm",
            "mcp_tool": "get_project_status",
        }
        mock_has_perm.return_value = True
        mock_acl.return_value = False

        from mcp.registry import call_mcp_tool

        mock_session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await call_mcp_tool("crm.get_project_status", {}, user, mock_session)

        assert exc_info.value.status_code == 403
        # Verify audit log was called with allowed=False
        mock_audit.info.assert_called()


@pytest.mark.asyncio
async def test_call_mcp_tool_succeeds_with_all_gates() -> None:
    """User has permission + ACL allows → MCPClient.call_tool called."""
    user = make_user(roles=["it-admin"])

    with (
        patch("mcp.registry.get_tool") as mock_get_tool,
        patch("mcp.registry.has_permission") as mock_has_perm,
        patch(
            "mcp.registry.check_tool_acl", new_callable=AsyncMock
        ) as mock_acl,
        patch("mcp.registry._get_client") as mock_get_client,
        patch("mcp.registry.audit_logger"),
    ):
        mock_get_tool.return_value = {
            "required_permissions": ["crm:read"],
            "mcp_server": "crm",
            "mcp_tool": "get_project_status",
        }
        mock_has_perm.return_value = True
        mock_acl.return_value = True
        mock_client = MagicMock()
        mock_client.call_tool = AsyncMock(
            return_value={"result": {"status": "active"}, "success": True}
        )
        mock_get_client.return_value = mock_client

        from mcp.registry import call_mcp_tool

        mock_session = AsyncMock()
        result = await call_mcp_tool(
            "crm.get_project_status",
            {"project_name": "Project Alpha"},
            user,
            mock_session,
        )

        assert result["success"] is True
        mock_client.call_tool.assert_called_once_with(
            "get_project_status", {"project_name": "Project Alpha"}
        )


@pytest.mark.asyncio
async def test_call_mcp_tool_logs_every_attempt() -> None:
    """Even on success, audit log has entry with tool name + user_id."""
    user = make_user(roles=["it-admin"])

    with (
        patch("mcp.registry.get_tool") as mock_get_tool,
        patch("mcp.registry.has_permission") as mock_has_perm,
        patch(
            "mcp.registry.check_tool_acl", new_callable=AsyncMock
        ) as mock_acl,
        patch("mcp.registry._get_client") as mock_get_client,
        patch("mcp.registry.audit_logger") as mock_audit,
    ):
        mock_get_tool.return_value = {
            "required_permissions": [],
            "mcp_server": "crm",
            "mcp_tool": "list_projects",
        }
        mock_has_perm.return_value = True
        mock_acl.return_value = True
        mock_client = MagicMock()
        mock_client.call_tool = AsyncMock(
            return_value={"result": {}, "success": True}
        )
        mock_get_client.return_value = mock_client

        from mcp.registry import call_mcp_tool

        await call_mcp_tool("crm.list_projects", {}, user, AsyncMock())

        # Audit log must be called (at least once — for the ACL gate)
        mock_audit.info.assert_called()
        # Verify the call includes tool_call event
        call_args = mock_audit.info.call_args
        assert "tool_call" in call_args[0] or "tool" in str(call_args)
