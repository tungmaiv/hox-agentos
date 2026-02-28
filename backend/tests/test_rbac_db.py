"""
DB-backed RBAC test suite — tests for has_permission with DB session,
check_artifact_permission, and cache invalidation.

Uses in-memory SQLite (via aiosqlite) so no real PostgreSQL is needed.
Seeds role_permissions with the same values as the hardcoded ROLE_PERMISSIONS dict,
then tests DB-backed permission checks, artifact permissions with staged status
model, per-user overrides, and cache behavior.
"""
import time
from uuid import uuid4

import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db import Base
from core.models.artifact_permission import ArtifactPermission
from core.models.role_permission import RolePermission
from core.models.user import UserContext
from core.models.user_artifact_permission import UserArtifactPermission


def make_ctx(roles: list[str]) -> UserContext:
    """Build a minimal UserContext with the given roles for RBAC testing."""
    return UserContext(
        user_id=uuid4(),
        email="test@blitz.local",
        username="testuser",
        roles=roles,
        groups=[],
    )


@pytest.fixture
async def db_session() -> AsyncSession:
    """
    Provide an in-memory SQLite async session with all tables created.
    Seeds role_permissions with employee and it-admin roles.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        # Seed role_permissions: employee role
        employee_perms = ["chat", "tool:email", "tool:calendar", "tool:project", "crm:read"]
        for perm in employee_perms:
            await session.execute(
                insert(RolePermission).values(
                    id=uuid4(), role="employee", permission=perm
                )
            )
        # Seed role_permissions: it-admin role (all permissions including registry:manage)
        admin_perms = [
            "chat", "tool:email", "tool:calendar", "tool:project",
            "crm:read", "crm:write", "tool:reports", "workflow:create",
            "workflow:approve", "tool:admin", "sandbox:execute", "registry:manage",
        ]
        for perm in admin_perms:
            await session.execute(
                insert(RolePermission).values(
                    id=uuid4(), role="it-admin", permission=perm
                )
            )
        await session.commit()
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# DB-backed has_permission tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_employee_has_chat_db(db_session: AsyncSession) -> None:
    """Employee role has chat permission when checked via DB."""
    from security.rbac import has_permission, invalidate_permission_cache

    invalidate_permission_cache()
    ctx = make_ctx(["employee"])
    assert await has_permission(ctx, "chat", db_session) is True


@pytest.mark.asyncio
async def test_employee_lacks_registry_manage_db(db_session: AsyncSession) -> None:
    """Employee role does NOT have registry:manage permission."""
    from security.rbac import has_permission, invalidate_permission_cache

    invalidate_permission_cache()
    ctx = make_ctx(["employee"])
    assert await has_permission(ctx, "registry:manage", db_session) is False


@pytest.mark.asyncio
async def test_it_admin_has_registry_manage_db(db_session: AsyncSession) -> None:
    """it-admin role has registry:manage permission via DB."""
    from security.rbac import has_permission, invalidate_permission_cache

    invalidate_permission_cache()
    ctx = make_ctx(["it-admin"])
    assert await has_permission(ctx, "registry:manage", db_session) is True


@pytest.mark.asyncio
async def test_unknown_role_has_no_perms_db(db_session: AsyncSession) -> None:
    """Unknown role has no permissions in DB (deny by default)."""
    from security.rbac import has_permission, invalidate_permission_cache

    invalidate_permission_cache()
    ctx = make_ctx(["unknown-role"])
    assert await has_permission(ctx, "chat", db_session) is False


# ---------------------------------------------------------------------------
# Artifact permission tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_artifact_permission_default_allow(db_session: AsyncSession) -> None:
    """No artifact_permissions rows = default ALLOW."""
    from security.rbac import check_artifact_permission

    ctx = make_ctx(["employee"])
    artifact_id = uuid4()
    result = await check_artifact_permission(ctx, "tool", artifact_id, db_session)
    assert result is True


@pytest.mark.asyncio
async def test_artifact_permission_explicit_deny(db_session: AsyncSession) -> None:
    """Artifact permission row with allowed=False for user's role = DENY."""
    from security.rbac import check_artifact_permission

    ctx = make_ctx(["employee"])
    artifact_id = uuid4()

    await db_session.execute(
        insert(ArtifactPermission).values(
            id=uuid4(),
            artifact_type="tool",
            artifact_id=artifact_id,
            role="employee",
            allowed=False,
            status="active",
        )
    )
    await db_session.commit()

    result = await check_artifact_permission(ctx, "tool", artifact_id, db_session)
    assert result is False


@pytest.mark.asyncio
async def test_artifact_permission_pending_ignored(db_session: AsyncSession) -> None:
    """Staged pending rows are ignored -- only status='active' checked."""
    from security.rbac import check_artifact_permission

    ctx = make_ctx(["employee"])
    artifact_id = uuid4()

    # Insert a deny row with status='pending' (staged, not yet confirmed by admin)
    await db_session.execute(
        insert(ArtifactPermission).values(
            id=uuid4(),
            artifact_type="tool",
            artifact_id=artifact_id,
            role="employee",
            allowed=False,
            status="pending",
        )
    )
    await db_session.commit()

    # Should still be allowed (pending row ignored)
    result = await check_artifact_permission(ctx, "tool", artifact_id, db_session)
    assert result is True


@pytest.mark.asyncio
async def test_user_artifact_permission_override(db_session: AsyncSession) -> None:
    """Per-user override takes precedence over role-level permission."""
    from security.rbac import check_artifact_permission

    user_id = uuid4()
    ctx = UserContext(
        user_id=user_id,
        email="test@blitz.local",
        username="testuser",
        roles=["employee"],
        groups=[],
    )
    artifact_id = uuid4()

    # Role-level: deny employee access to this tool
    await db_session.execute(
        insert(ArtifactPermission).values(
            id=uuid4(),
            artifact_type="tool",
            artifact_id=artifact_id,
            role="employee",
            allowed=False,
            status="active",
        )
    )
    # User-level: override to allow this specific user
    await db_session.execute(
        insert(UserArtifactPermission).values(
            id=uuid4(),
            artifact_type="tool",
            artifact_id=artifact_id,
            user_id=user_id,
            allowed=True,
            status="active",
        )
    )
    await db_session.commit()

    # User override (allow) takes precedence over role deny
    result = await check_artifact_permission(ctx, "tool", artifact_id, db_session)
    assert result is True


@pytest.mark.asyncio
async def test_user_artifact_permission_pending_not_override(db_session: AsyncSession) -> None:
    """Per-user override with status='pending' does NOT take effect."""
    from security.rbac import check_artifact_permission

    user_id = uuid4()
    ctx = UserContext(
        user_id=user_id,
        email="test@blitz.local",
        username="testuser",
        roles=["employee"],
        groups=[],
    )
    artifact_id = uuid4()

    # Role-level: deny employee access
    await db_session.execute(
        insert(ArtifactPermission).values(
            id=uuid4(),
            artifact_type="tool",
            artifact_id=artifact_id,
            role="employee",
            allowed=False,
            status="active",
        )
    )
    # User-level: allow but staged (pending)
    await db_session.execute(
        insert(UserArtifactPermission).values(
            id=uuid4(),
            artifact_type="tool",
            artifact_id=artifact_id,
            user_id=user_id,
            allowed=True,
            status="pending",
        )
    )
    await db_session.commit()

    # Pending user override is ignored; role deny applies
    result = await check_artifact_permission(ctx, "tool", artifact_id, db_session)
    assert result is False


# ---------------------------------------------------------------------------
# Cache invalidation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_invalidation_triggers_refresh(db_session: AsyncSession) -> None:
    """After invalidate_permission_cache(), next call refreshes from DB."""
    from security.rbac import (
        _cache_timestamp,
        _permission_cache,
        has_permission,
        invalidate_permission_cache,
    )

    invalidate_permission_cache()
    ctx = make_ctx(["employee"])

    # First call: loads from DB, populates cache
    result1 = await has_permission(ctx, "chat", db_session)
    assert result1 is True

    # Cache should now be populated
    from security import rbac
    assert rbac._cache_timestamp > 0
    assert "employee" in rbac._permission_cache

    # Invalidate and verify timestamp reset
    invalidate_permission_cache()
    assert rbac._cache_timestamp == 0.0

    # Next call should refresh from DB again (still returns correct result)
    result2 = await has_permission(ctx, "chat", db_session)
    assert result2 is True
    assert rbac._cache_timestamp > 0


@pytest.mark.asyncio
async def test_fallback_to_dict_when_no_session() -> None:
    """When session=None, has_permission uses hardcoded ROLE_PERMISSIONS dict."""
    from security.rbac import has_permission

    ctx = make_ctx(["employee"])
    # session=None triggers sync fallback
    result = await has_permission(ctx, "chat", None)
    assert result is True
    result2 = await has_permission(ctx, "registry:manage", None)
    assert result2 is False
