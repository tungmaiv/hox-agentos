"""
Local authentication test suite.

Tests cover:
  1. JWT issue and validation (HS256 create + verify)
  2. Dual-issuer dispatch (local HS256 vs Keycloak RS256)
  3. Password hashing
  4. Login endpoint (valid/invalid/deactivated)
  5. Admin CRUD (user + group create, list, update, delete)
  6. RBAC gate (403 for non-admin)
  7. Role resolution (union of group + direct roles)

Test infrastructure:
  - Uses an in-memory SQLite DB per test function (not module-scoped to avoid fixture scope issues)
  - Mocks get_current_user for admin-gated endpoints
  - LOCAL_JWT_SECRET set in conftest.py _TEST_ENV dict (applied before settings instantiation)

No real PostgreSQL or Keycloak needed — all mocked.
"""
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from core.db import Base
from core.models.local_auth import (
    LocalGroup,
    LocalGroupRole,
    LocalUser,
    LocalUserGroup,
    LocalUserRole,
)
from core.models.user import UserContext
from security.local_auth import (
    create_local_token,
    hash_password,
    resolve_user_roles,
    verify_password,
)


# ---------------------------------------------------------------------------
# Test DB fixtures (SQLite in-memory)
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_engine():
    """Create an in-memory SQLite engine for each test function."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Enable foreign key enforcement in SQLite
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(conn, _):
        conn.execute("PRAGMA foreign_keys = ON")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Provide a per-test DB session."""
    async_session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


async def _create_test_user(
    session: AsyncSession,
    username: str = "testuser",
    email: str = "test@example.com",
    password: str = "Password1",
    is_active: bool = True,
) -> LocalUser:
    user = LocalUser(
        username=username,
        email=email,
        password_hash=hash_password(password),
        is_active=is_active,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _create_test_group(
    session: AsyncSession,
    name: str = "testgroup",
    roles: list[str] | None = None,
) -> LocalGroup:
    group = LocalGroup(name=name, description="Test group")
    session.add(group)
    await session.flush()
    for role in (roles or []):
        session.add(LocalGroupRole(group_id=group.id, role=role))
    await session.commit()
    await session.refresh(group)
    return group


# ---------------------------------------------------------------------------
# Password tests
# ---------------------------------------------------------------------------


def test_hash_and_verify_password() -> None:
    """hash_password + verify_password round-trip succeeds; wrong password fails."""
    plain = "SecurePass1"
    hashed = hash_password(plain)

    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPass1", hashed) is False
    assert verify_password("", hashed) is False


def test_verify_different_hashes_of_same_password() -> None:
    """Two bcrypt hashes of the same password should both verify correctly."""
    plain = "Password1"
    h1 = hash_password(plain)
    h2 = hash_password(plain)
    assert h1 != h2  # bcrypt uses random salt
    assert verify_password(plain, h1) is True
    assert verify_password(plain, h2) is True


# ---------------------------------------------------------------------------
# JWT creation and validation tests
# ---------------------------------------------------------------------------


def test_create_local_token_returns_valid_jwt() -> None:
    """create_local_token returns a HS256 JWT with correct claims."""
    from jose import jwt as jose_jwt

    user_id = uuid4()
    token = create_local_token(
        user_id=user_id,
        email="alice@example.com",
        username="alice",
        roles=["employee", "it-admin"],
    )

    # Decode without verification to check structure
    payload = jose_jwt.get_unverified_claims(token)
    assert payload["sub"] == str(user_id)
    assert payload["iss"] == "blitz-local"
    assert payload["email"] == "alice@example.com"
    assert payload["preferred_username"] == "alice"
    assert set(payload["realm_roles"]) == {"employee", "it-admin"}
    assert "exp" in payload
    assert "iat" in payload
    # Token should not be expired (iat < now + 30 seconds)
    assert payload["iat"] <= int(time.time()) + 1


def test_create_local_token_missing_secret_raises_500(monkeypatch) -> None:
    """create_local_token raises 500 when LOCAL_JWT_SECRET is not configured."""
    monkeypatch.setattr("security.local_auth.settings.local_jwt_secret", "")
    with pytest.raises(HTTPException) as exc_info:
        create_local_token(uuid4(), "e@x.com", "user", [])
    assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# Dual-issuer JWT dispatch tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_token_routes_local_issuer(db_session) -> None:
    """validate_token() dispatches to local HS256 path when iss=blitz-local."""
    from security.jwt import validate_token
    from security.local_auth import validate_local_token

    user = await _create_test_user(db_session, username="localuser", email="local@example.com")
    token = create_local_token(user.id, user.email, user.username, ["employee"])

    ctx = await validate_token(token, session=db_session)
    assert ctx["user_id"] == user.id
    assert ctx["username"] == "localuser"
    assert "employee" in ctx["roles"]


@pytest.mark.asyncio
async def test_validate_token_routes_keycloak_issuer() -> None:
    """validate_token() dispatches to Keycloak RS256 path when iss=Keycloak URL."""
    from unittest.mock import AsyncMock, patch

    from security.jwt import validate_token

    mock_ctx = UserContext(
        user_id=uuid4(),
        email="kc@example.com",
        username="kcuser",
        roles=["employee"],
        groups=[],
    )
    with patch("security.jwt._validate_keycloak_token", new_callable=AsyncMock, return_value=mock_ctx) as mock_kc:
        from core.config import settings
        from jose import jwt as jose_jwt

        # Build a token that claims Keycloak issuer (signature doesn't matter for dispatch peek)
        # We just need a valid JWT structure — actual validation is mocked
        fake_payload = {
            "sub": str(uuid4()),
            "iss": settings.keycloak_issuer,
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
        # Use HS256 just to create a valid JWT structure — mock will intercept before RS256 verify
        token = jose_jwt.encode(fake_payload, "anysecret", algorithm="HS256")
        ctx = await validate_token(token)

    mock_kc.assert_called_once_with(token)
    assert ctx["email"] == "kc@example.com"


@pytest.mark.asyncio
async def test_validate_token_unknown_issuer_returns_401(db_session) -> None:
    """validate_token() raises 401 when issuer is neither Keycloak nor blitz-local."""
    from jose import jwt as jose_jwt

    from security.jwt import validate_token

    fake_token = jose_jwt.encode(
        {"sub": str(uuid4()), "iss": "https://evil.example.com", "exp": int(time.time()) + 3600},
        "anysecret",
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc_info:
        await validate_token(fake_token, session=db_session)
    assert exc_info.value.status_code == 401
    assert "unknown" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_validate_local_token_deactivated_user_returns_401(db_session) -> None:
    """validate_local_token() returns 401 when user.is_active is False."""
    from security.local_auth import validate_local_token

    user = await _create_test_user(
        db_session, username="inactive", email="inactive@example.com", is_active=False
    )
    token = create_local_token(user.id, user.email, user.username, [])

    with pytest.raises(HTTPException) as exc_info:
        await validate_local_token(token, db_session)
    assert exc_info.value.status_code == 401
    assert "deactivated" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_validate_local_token_expired_returns_401(db_session) -> None:
    """validate_local_token() returns 401 when token is expired."""
    from jose import jwt as jose_jwt

    from security.local_auth import validate_local_token

    user_id = uuid4()
    # Create an already-expired token
    payload = {
        "sub": str(user_id),
        "iss": "blitz-local",
        "exp": int(time.time()) - 10,
        "iat": int(time.time()) - 3610,
        "email": "x@y.com",
        "preferred_username": "x",
        "realm_roles": [],
    }
    from core.config import settings
    expired_token = jose_jwt.encode(payload, settings.local_jwt_secret, algorithm="HS256")

    with pytest.raises(HTTPException) as exc_info:
        await validate_local_token(expired_token, db_session)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Role resolution tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_roles_union_of_group_and_direct(db_session) -> None:
    """resolve_user_roles returns union of group roles + direct user roles."""
    user = await _create_test_user(db_session, username="roleuser", email="role@example.com")
    group = await _create_test_group(db_session, name="engineers", roles=["employee"])

    # Add user to group
    db_session.add(LocalUserGroup(user_id=user.id, group_id=group.id))
    # Add direct role
    db_session.add(LocalUserRole(user_id=user.id, role="it-admin"))
    await db_session.commit()

    roles = await resolve_user_roles(db_session, user.id)
    assert "employee" in roles  # from group
    assert "it-admin" in roles  # direct
    assert roles == sorted(roles)  # must be sorted


@pytest.mark.asyncio
async def test_resolve_roles_no_duplicates(db_session) -> None:
    """resolve_user_roles deduplicates when the same role appears in multiple groups."""
    user = await _create_test_user(db_session, username="dupuser", email="dup@example.com")
    group1 = await _create_test_group(db_session, name="group_alpha", roles=["employee"])
    group2 = await _create_test_group(db_session, name="group_beta", roles=["employee"])

    db_session.add(LocalUserGroup(user_id=user.id, group_id=group1.id))
    db_session.add(LocalUserGroup(user_id=user.id, group_id=group2.id))
    await db_session.commit()

    roles = await resolve_user_roles(db_session, user.id)
    assert roles.count("employee") == 1  # deduplicated


@pytest.mark.asyncio
async def test_resolve_roles_no_roles_returns_empty(db_session) -> None:
    """resolve_user_roles returns empty list for a user with no role assignments."""
    user = await _create_test_user(db_session, username="noroles", email="noroles@example.com")
    roles = await resolve_user_roles(db_session, user.id)
    assert roles == []


# ---------------------------------------------------------------------------
# Login endpoint tests (FastAPI TestClient with mock DB)
# ---------------------------------------------------------------------------


def _make_test_app(db_session: AsyncSession) -> FastAPI:
    """Create a minimal FastAPI app with the login router, using mock DB."""
    from api.routes.auth_local import router as auth_router

    app = FastAPI()
    app.include_router(auth_router)

    # Override get_db to return the test session
    from core.db import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.mark.asyncio
async def test_login_valid_credentials_returns_token(db_session) -> None:
    """POST /api/auth/local/token with valid credentials returns access_token."""
    from jose import jwt as jose_jwt
    from core.config import settings
    from httpx import AsyncClient, ASGITransport

    user = await _create_test_user(
        db_session,
        username="loginuser",
        email="login@example.com",
        password="Correct1",
        is_active=True,
    )
    app = _make_test_app(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/local/token",
            json={"username": "loginuser", "password": "Correct1"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"

    # Verify token claims
    payload = jose_jwt.decode(
        body["access_token"],
        settings.local_jwt_secret,
        algorithms=["HS256"],
        issuer="blitz-local",
    )
    assert payload["sub"] == str(user.id)
    assert payload["email"] == "login@example.com"


@pytest.mark.asyncio
async def test_login_invalid_password_returns_401(db_session) -> None:
    """POST /api/auth/local/token with wrong password returns 401."""
    from httpx import AsyncClient, ASGITransport

    await _create_test_user(
        db_session, username="pwduser", email="pwd@example.com", password="Correct1"
    )
    app = _make_test_app(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/local/token",
            json={"username": "pwduser", "password": "WrongPass1"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user_returns_401(db_session) -> None:
    """POST /api/auth/local/token with unknown username returns 401."""
    from httpx import AsyncClient, ASGITransport

    app = _make_test_app(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/local/token",
            json={"username": "nobody_here", "password": "SomePass1"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_deactivated_user_returns_401(db_session) -> None:
    """POST /api/auth/local/token with deactivated account returns 401."""
    from httpx import AsyncClient, ASGITransport

    await _create_test_user(
        db_session,
        username="deactuser",
        email="deact@example.com",
        password="Password1",
        is_active=False,
    )
    app = _make_test_app(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/local/token",
            json={"username": "deactuser", "password": "Password1"},
        )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Admin CRUD tests
# ---------------------------------------------------------------------------


def _make_admin_app(db_session: AsyncSession, admin_user: UserContext) -> FastAPI:
    """Create a minimal FastAPI app with admin router, mock auth + DB."""
    from api.routes.admin_local_users import router as admin_router

    app = FastAPI()
    app.include_router(admin_router)

    from core.db import get_db
    from security.deps import get_current_user

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return admin_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return app


@pytest.fixture
def admin_user_ctx() -> UserContext:
    """UserContext for a user with registry:manage permission (it-admin role)."""
    return UserContext(
        user_id=uuid4(),
        email="admin@example.com",
        username="admin",
        roles=["it-admin"],
        groups=[],
    )


@pytest.mark.asyncio
async def test_create_user_success(db_session, admin_user_ctx) -> None:
    """POST /api/admin/local/users creates a user and returns full response."""
    from httpx import AsyncClient, ASGITransport
    from security.rbac import has_permission

    with patch("api.routes.admin_local_users.has_permission", new_callable=AsyncMock, return_value=True):
        app = _make_admin_app(db_session, admin_user_ctx)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/admin/local/users",
                json={
                    "username": "newuser",
                    "email": "new@example.com",
                    "password": "NewPass1",
                },
            )

    assert resp.status_code == 201, f"Expected 201 but got {resp.status_code}: {resp.json()}"
    body = resp.json()
    assert body["username"] == "newuser"
    assert body["email"] == "new@example.com"
    assert body["is_active"] is True
    assert "password" not in body
    assert "password_hash" not in body


@pytest.mark.asyncio
async def test_create_user_duplicate_username_returns_409(db_session, admin_user_ctx) -> None:
    """POST /api/admin/local/users with duplicate username returns 409."""
    from httpx import AsyncClient, ASGITransport

    await _create_test_user(db_session, username="dupname", email="dupname@example.com")

    with patch("api.routes.admin_local_users.has_permission", new_callable=AsyncMock, return_value=True):
        app = _make_admin_app(db_session, admin_user_ctx)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/admin/local/users",
                json={
                    "username": "dupname",
                    "email": "different@example.com",
                    "password": "NewPass1",
                },
            )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_users_returns_resolved_roles(db_session, admin_user_ctx) -> None:
    """GET /api/admin/local/users returns users with resolved roles."""
    from httpx import AsyncClient, ASGITransport

    user = await _create_test_user(db_session, username="listroles", email="listroles@example.com")
    group = await _create_test_group(db_session, name="listroles_group", roles=["employee"])
    db_session.add(LocalUserGroup(user_id=user.id, group_id=group.id))
    await db_session.commit()

    with patch("api.routes.admin_local_users.has_permission", new_callable=AsyncMock, return_value=True):
        app = _make_admin_app(db_session, admin_user_ctx)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/admin/local/users")

    assert resp.status_code == 200
    users = resp.json()
    list_user = next((u for u in users if u["username"] == "listroles"), None)
    assert list_user is not None
    assert "employee" in list_user["roles"]


@pytest.mark.asyncio
async def test_create_group_success(db_session, admin_user_ctx) -> None:
    """POST /api/admin/local/groups creates a group with roles."""
    from httpx import AsyncClient, ASGITransport

    with patch("api.routes.admin_local_users.has_permission", new_callable=AsyncMock, return_value=True):
        app = _make_admin_app(db_session, admin_user_ctx)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/admin/local/groups",
                json={"name": "newgroup", "description": "Test group", "roles": ["employee"]},
            )

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "newgroup"
    assert "employee" in body["roles"]
    assert body["member_count"] == 0


@pytest.mark.asyncio
async def test_assign_user_to_group_inherits_roles(db_session, admin_user_ctx) -> None:
    """After assigning a user to a group, their resolved roles include the group's roles."""
    from httpx import AsyncClient, ASGITransport

    user = await _create_test_user(db_session, username="groupinherit", email="gi@example.com")
    group = await _create_test_group(db_session, name="inherit_group", roles=["developer"])

    with patch("api.routes.admin_local_users.has_permission", new_callable=AsyncMock, return_value=True):
        app = _make_admin_app(db_session, admin_user_ctx)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Assign user to group
            resp = await client.post(
                f"/api/admin/local/users/{user.id}/groups",
                json={"group_ids": [str(group.id)]},
            )
            assert resp.status_code == 204

            # Get user and check resolved roles
            resp = await client.get(f"/api/admin/local/users/{user.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert "developer" in body["roles"]


@pytest.mark.asyncio
async def test_delete_user_cascades(db_session, admin_user_ctx) -> None:
    """DELETE /api/admin/local/users/{id} removes user and all associations."""
    from httpx import AsyncClient, ASGITransport
    from sqlalchemy import select

    user = await _create_test_user(db_session, username="todelete", email="del@example.com")
    group = await _create_test_group(db_session, name="del_group", roles=["employee"])
    db_session.add(LocalUserGroup(user_id=user.id, group_id=group.id))
    db_session.add(LocalUserRole(user_id=user.id, role="it-admin"))
    await db_session.commit()

    with patch("api.routes.admin_local_users.has_permission", new_callable=AsyncMock, return_value=True):
        app = _make_admin_app(db_session, admin_user_ctx)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(f"/api/admin/local/users/{user.id}")
    assert resp.status_code == 204

    # Verify user is gone
    result = await db_session.execute(select(LocalUser).where(LocalUser.id == user.id))
    assert result.scalar_one_or_none() is None

    # Verify group memberships and direct roles are gone (CASCADE)
    membership = await db_session.execute(
        select(LocalUserGroup).where(LocalUserGroup.user_id == user.id)
    )
    assert membership.scalar_one_or_none() is None

    user_role = await db_session.execute(
        select(LocalUserRole).where(LocalUserRole.user_id == user.id)
    )
    assert user_role.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_admin_endpoints_require_registry_manage(db_session) -> None:
    """Non-admin user (no registry:manage) gets 403 on admin endpoints."""
    from httpx import AsyncClient, ASGITransport

    non_admin = UserContext(
        user_id=uuid4(),
        email="noadmin@example.com",
        username="noadmin",
        roles=["employee"],
        groups=[],
    )
    # has_permission returns False for non-admin
    with patch("api.routes.admin_local_users.has_permission", new_callable=AsyncMock, return_value=False):
        app = _make_admin_app(db_session, non_admin)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/admin/local/users")
    assert resp.status_code == 403
