"""
RBAC test suite -- Gate 2 security coverage.

Tests cover all 5 roles and edge cases from the hardcoded ROLE_PERMISSIONS fallback.
All tests pass session=None to trigger the dict-based fallback path,
preserving existing test behavior without a DB.

Roles tested:
  employee    -> chat, tool:email, tool:calendar, tool:project
  manager     -> all employee + tool:reports, workflow:create
  team-lead   -> all manager + workflow:approve
  it-admin    -> all permissions + tool:admin, sandbox:execute, registry:manage
  executive   -> chat, tool:reports (read-only -- no email, calendar, project)

Multi-role union and unknown-role are also tested.
"""
import pytest
from uuid import uuid4

from core.models.user import UserContext


def make_ctx(roles: list[str]) -> UserContext:
    """Build a minimal UserContext with the given roles for RBAC testing."""
    return UserContext(
        user_id=uuid4(),
        email="test@blitz.local",
        username="testuser",
        roles=roles,
        groups=[],
    )


# ---------------------------------------------------------------------------
# employee role tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_employee_has_chat() -> None:
    from security.rbac import has_permission

    ctx = make_ctx(["employee"])
    assert await has_permission(ctx, "chat") is True


@pytest.mark.asyncio
async def test_employee_has_tool_email() -> None:
    from security.rbac import has_permission

    ctx = make_ctx(["employee"])
    assert await has_permission(ctx, "tool:email") is True


@pytest.mark.asyncio
async def test_employee_has_tool_calendar() -> None:
    from security.rbac import has_permission

    ctx = make_ctx(["employee"])
    assert await has_permission(ctx, "tool:calendar") is True


@pytest.mark.asyncio
async def test_employee_has_tool_project() -> None:
    from security.rbac import has_permission

    ctx = make_ctx(["employee"])
    assert await has_permission(ctx, "tool:project") is True


@pytest.mark.asyncio
async def test_employee_lacks_tool_admin() -> None:
    from security.rbac import has_permission

    ctx = make_ctx(["employee"])
    assert await has_permission(ctx, "tool:admin") is False


@pytest.mark.asyncio
async def test_employee_lacks_workflow_create() -> None:
    from security.rbac import has_permission

    ctx = make_ctx(["employee"])
    assert await has_permission(ctx, "workflow:create") is False


@pytest.mark.asyncio
async def test_employee_lacks_sandbox_execute() -> None:
    from security.rbac import has_permission

    ctx = make_ctx(["employee"])
    assert await has_permission(ctx, "sandbox:execute") is False


# ---------------------------------------------------------------------------
# manager role tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manager_has_all_employee_plus_reports_and_workflow_create() -> None:
    """Manager inherits all employee permissions and adds tool:reports + workflow:create."""
    from security.rbac import has_permission

    ctx = make_ctx(["manager"])
    # Inherited from employee
    assert await has_permission(ctx, "chat") is True
    assert await has_permission(ctx, "tool:email") is True
    assert await has_permission(ctx, "tool:calendar") is True
    assert await has_permission(ctx, "tool:project") is True
    # Manager-specific
    assert await has_permission(ctx, "tool:reports") is True
    assert await has_permission(ctx, "workflow:create") is True
    # Manager does not have workflow:approve or admin tools
    assert await has_permission(ctx, "workflow:approve") is False
    assert await has_permission(ctx, "tool:admin") is False


# ---------------------------------------------------------------------------
# team-lead role tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_team_lead_has_workflow_approve() -> None:
    from security.rbac import has_permission

    ctx = make_ctx(["team-lead"])
    assert await has_permission(ctx, "workflow:approve") is True


@pytest.mark.asyncio
async def test_team_lead_has_all_manager_permissions() -> None:
    """Team-lead inherits all manager permissions."""
    from security.rbac import has_permission

    ctx = make_ctx(["team-lead"])
    assert await has_permission(ctx, "chat") is True
    assert await has_permission(ctx, "tool:email") is True
    assert await has_permission(ctx, "tool:reports") is True
    assert await has_permission(ctx, "workflow:create") is True
    assert await has_permission(ctx, "workflow:approve") is True
    # team-lead does not have admin tools
    assert await has_permission(ctx, "tool:admin") is False


# ---------------------------------------------------------------------------
# it-admin role tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_it_admin_has_sandbox_execute() -> None:
    from security.rbac import has_permission

    ctx = make_ctx(["it-admin"])
    assert await has_permission(ctx, "sandbox:execute") is True


@pytest.mark.asyncio
async def test_it_admin_has_all_permissions() -> None:
    """it-admin has every permission including admin-only ones."""
    from security.rbac import has_permission

    ctx = make_ctx(["it-admin"])
    assert await has_permission(ctx, "chat") is True
    assert await has_permission(ctx, "tool:email") is True
    assert await has_permission(ctx, "tool:calendar") is True
    assert await has_permission(ctx, "tool:project") is True
    assert await has_permission(ctx, "tool:reports") is True
    assert await has_permission(ctx, "workflow:create") is True
    assert await has_permission(ctx, "workflow:approve") is True
    assert await has_permission(ctx, "tool:admin") is True
    assert await has_permission(ctx, "sandbox:execute") is True
    assert await has_permission(ctx, "registry:manage") is True


# ---------------------------------------------------------------------------
# executive role tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executive_has_chat_and_tool_reports_only() -> None:
    """Executive can only chat and view reports -- nothing else."""
    from security.rbac import has_permission

    ctx = make_ctx(["executive"])
    assert await has_permission(ctx, "chat") is True
    assert await has_permission(ctx, "tool:reports") is True


@pytest.mark.asyncio
async def test_executive_lacks_tool_email() -> None:
    from security.rbac import has_permission

    ctx = make_ctx(["executive"])
    assert await has_permission(ctx, "tool:email") is False


@pytest.mark.asyncio
async def test_executive_lacks_tool_calendar() -> None:
    from security.rbac import has_permission

    ctx = make_ctx(["executive"])
    assert await has_permission(ctx, "tool:calendar") is False


@pytest.mark.asyncio
async def test_executive_lacks_workflow_create() -> None:
    from security.rbac import has_permission

    ctx = make_ctx(["executive"])
    assert await has_permission(ctx, "workflow:create") is False


@pytest.mark.asyncio
async def test_executive_lacks_sandbox_execute() -> None:
    from security.rbac import has_permission

    ctx = make_ctx(["executive"])
    assert await has_permission(ctx, "sandbox:execute") is False


# ---------------------------------------------------------------------------
# Multi-role and edge case tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multi_role_union_employee_and_manager() -> None:
    """User with both employee and manager roles has union of all their permissions."""
    from security.rbac import has_permission

    ctx = make_ctx(["employee", "manager"])
    # From employee
    assert await has_permission(ctx, "tool:email") is True
    # From manager (not in employee)
    assert await has_permission(ctx, "workflow:create") is True
    # Neither has workflow:approve
    assert await has_permission(ctx, "workflow:approve") is False


@pytest.mark.asyncio
async def test_unknown_role_has_no_permissions() -> None:
    """An unrecognized role grants no permissions -- deny by default."""
    from security.rbac import has_permission

    ctx = make_ctx(["superuser-nonexistent"])
    assert await has_permission(ctx, "chat") is False
    assert await has_permission(ctx, "tool:admin") is False
    assert await has_permission(ctx, "sandbox:execute") is False


@pytest.mark.asyncio
async def test_empty_roles_has_no_permissions() -> None:
    """A user with no roles has no permissions."""
    from security.rbac import has_permission

    ctx = make_ctx([])
    assert await has_permission(ctx, "chat") is False


def test_get_permissions_returns_set() -> None:
    """get_permissions returns a set of permission strings for the given roles."""
    from security.rbac import get_permissions

    perms = get_permissions(["employee"])
    assert isinstance(perms, set)
    assert "chat" in perms
    assert "tool:email" in perms
    assert "tool:admin" not in perms


def test_get_permissions_union_multiple_roles() -> None:
    """get_permissions unions permissions for multiple roles."""
    from security.rbac import get_permissions

    perms = get_permissions(["employee", "manager"])
    # employee perms
    assert "tool:email" in perms
    # manager-only perms
    assert "workflow:create" in perms
    # neither has this
    assert "sandbox:execute" not in perms
