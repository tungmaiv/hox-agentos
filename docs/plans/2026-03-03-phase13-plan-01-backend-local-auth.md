# Phase 13 Plan 01: Backend Local Auth (DB + JWT + API)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Local users can be created in PostgreSQL, authenticate via username/password, and receive HS256 JWTs that pass through the existing 3-gate security system identically to Keycloak JWTs.

**Architecture:** Five new tables (`local_users`, `local_groups`, `local_user_groups`, `local_group_roles`, `local_user_roles`) store user/group/role data. A new `/auth/local/token` endpoint issues HS256 JWTs with `iss: "blitz-local"`. The existing `validate_token()` is refactored into an issuer-dispatch pattern — peeking at the unverified `iss` claim to route to either the existing Keycloak RS256 path or the new local HS256 path. Admin CRUD routes at `/api/admin/local/users` and `/api/admin/local/groups` provide full management.

**Tech Stack:** FastAPI, SQLAlchemy (async), Alembic, passlib[bcrypt], python-jose (HS256), Pydantic v2, pytest

**Design doc:** `docs/plans/2026-03-03-phase13-local-auth-design.md`

**Current test baseline:** Run `cd backend && PYTHONPATH=. .venv/bin/pytest tests/ -q` — note the count before starting.

---

### Task 1: Add passlib[bcrypt] Dependency

**Files:**
- Modify: `backend/pyproject.toml`

**Step 1: Add the dependency**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
uv add "passlib[bcrypt]"
```

If `uv add` hangs (known gotcha), add manually to pyproject.toml under `[project] dependencies`:

```
"passlib[bcrypt]>=1.7.4",
```

Then run:

```bash
uv sync
```

**Step 2: Verify import works**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/python -c "from passlib.hash import bcrypt; print(bcrypt.hash('test'))"
```

Expected: A bcrypt hash string like `$2b$12$...`

**Step 3: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "feat(13-01): add passlib[bcrypt] dependency for local auth"
```

---

### Task 2: Add LOCAL_JWT_SECRET and LOCAL_JWT_EXPIRES_HOURS to Settings

**Files:**
- Modify: `backend/core/config.py:15-75` (Settings class)
- Modify: `backend/tests/conftest.py:21-31` (_TEST_ENV dict)

**Step 1: Write the failing test**

Create `backend/tests/test_local_auth_config.py`:

```python
"""Test that local auth settings are present and have correct defaults."""


def test_local_jwt_secret_in_settings() -> None:
    from core.config import settings

    assert hasattr(settings, "local_jwt_secret")
    assert isinstance(settings.local_jwt_secret, str)


def test_local_jwt_expires_hours_default() -> None:
    from core.config import settings

    assert hasattr(settings, "local_jwt_expires_hours")
    assert settings.local_jwt_expires_hours == 8
```

**Step 2: Run test to verify it fails**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_local_auth_config.py -v
```

Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'local_jwt_secret'`

**Step 3: Add settings to config.py**

Add these two fields to the `Settings` class in `backend/core/config.py` after line 47 (`credential_encryption_key`):

```python
    # Local auth
    local_jwt_secret: str = ""  # HS256 signing key for local user JWTs (min 32 chars)
    local_jwt_expires_hours: int = 8  # Local JWT lifetime in hours (one workday)
```

**Step 4: Add test env var to conftest.py**

Add to `_TEST_ENV` dict in `backend/tests/conftest.py`:

```python
    "LOCAL_JWT_SECRET": "test-local-jwt-secret-key-32-chars-min!!",
```

**Step 5: Run test to verify it passes**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_local_auth_config.py -v
```

Expected: 2 passed

**Step 6: Run full test suite to confirm no regressions**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: All existing tests still pass.

**Step 7: Commit**

```bash
git add backend/core/config.py backend/tests/conftest.py backend/tests/test_local_auth_config.py
git commit -m "feat(13-01): add LOCAL_JWT_SECRET and LOCAL_JWT_EXPIRES_HOURS settings"
```

---

### Task 3: Create SQLAlchemy ORM Models for Local Auth Tables

**Files:**
- Create: `backend/core/models/local_auth.py`
- Modify: `backend/core/models/__init__.py` (add imports)

**Step 1: Write the failing test**

Create `backend/tests/test_local_auth_models.py`:

```python
"""Test local auth ORM models exist and have correct columns."""
import uuid
from datetime import datetime


def test_local_user_model_columns() -> None:
    from core.models.local_auth import LocalUser

    assert LocalUser.__tablename__ == "local_users"
    cols = {c.name for c in LocalUser.__table__.columns}
    assert cols >= {"id", "username", "email", "password_hash", "is_active", "created_at", "updated_at"}


def test_local_group_model_columns() -> None:
    from core.models.local_auth import LocalGroup

    assert LocalGroup.__tablename__ == "local_groups"
    cols = {c.name for c in LocalGroup.__table__.columns}
    assert cols >= {"id", "name", "description", "created_at"}


def test_local_user_group_model() -> None:
    from core.models.local_auth import LocalUserGroup

    assert LocalUserGroup.__tablename__ == "local_user_groups"
    cols = {c.name for c in LocalUserGroup.__table__.columns}
    assert cols >= {"user_id", "group_id"}


def test_local_group_role_model() -> None:
    from core.models.local_auth import LocalGroupRole

    assert LocalGroupRole.__tablename__ == "local_group_roles"
    cols = {c.name for c in LocalGroupRole.__table__.columns}
    assert cols >= {"group_id", "role"}


def test_local_user_role_model() -> None:
    from core.models.local_auth import LocalUserRole

    assert LocalUserRole.__tablename__ == "local_user_roles"
    cols = {c.name for c in LocalUserRole.__table__.columns}
    assert cols >= {"user_id", "role"}
```

**Step 2: Run test to verify it fails**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_local_auth_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'core.models.local_auth'`

**Step 3: Create the ORM models**

Create `backend/core/models/local_auth.py`:

```python
"""
Local auth ORM models — users, groups, and role assignments.

These tables are admin-managed (no RLS needed) and exist parallel to
Keycloak users. Local users authenticate via POST /auth/local/token
and receive HS256 JWTs that pass through the same 3-gate security
system as Keycloak RS256 JWTs.

Tables:
  local_users       — username/password accounts
  local_groups      — named groups with role assignments
  local_user_groups — M2M user ↔ group membership
  local_group_roles — M2M group → role
  local_user_roles  — direct user → role (overrides)
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class LocalUser(Base):
    """Local user account with bcrypt password hash."""

    __tablename__ = "local_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class LocalGroup(Base):
    """Named group for organizing local users and assigning roles."""

    __tablename__ = "local_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LocalUserGroup(Base):
    """M2M: user membership in a group."""

    __tablename__ = "local_user_groups"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("local_users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("local_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )


class LocalGroupRole(Base):
    """M2M: role assigned to a group. All group members inherit these roles."""

    __tablename__ = "local_group_roles"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("local_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(64), primary_key=True)


class LocalUserRole(Base):
    """Direct role assignment to a user (bypasses group membership)."""

    __tablename__ = "local_user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("local_users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(64), primary_key=True)
```

**Step 4: Register models in `__init__.py`**

Add to `backend/core/models/__init__.py`:

```python
from core.models.local_auth import (  # noqa: F401
    LocalGroup,
    LocalGroupRole,
    LocalUser,
    LocalUserGroup,
    LocalUserRole,
)
```

**Step 5: Run test to verify it passes**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_local_auth_models.py -v
```

Expected: 5 passed

**Step 6: Commit**

```bash
git add backend/core/models/local_auth.py backend/core/models/__init__.py backend/tests/test_local_auth_models.py
git commit -m "feat(13-01): add SQLAlchemy ORM models for local auth tables"
```

---

### Task 4: Create Alembic Migration 017

**Files:**
- Create: `backend/alembic/versions/017_local_auth_tables.py` (autogenerated)

**Step 1: Generate migration**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
.venv/bin/alembic revision --autogenerate -m "add local auth tables"
```

**Step 2: Review the generated migration**

Open the generated file and verify it creates all 5 tables: `local_users`, `local_groups`, `local_user_groups`, `local_group_roles`, `local_user_roles`. Check FK constraints and indexes.

**Step 3: Apply migration (via docker exec since Alembic needs DB access)**

```bash
# If running locally with DB access:
cd /home/tungmv/Projects/hox-agentos/backend
.venv/bin/alembic upgrade head

# Or via docker:
# docker exec -it blitz-backend .venv/bin/alembic upgrade head
```

**Step 4: Verify migration applied**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
.venv/bin/alembic current
```

Expected: Shows the new 017 revision as head.

**Step 5: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(13-01): add Alembic migration 017 for local auth tables"
```

---

### Task 5: Create Pydantic Schemas for Local Auth

**Files:**
- Create: `backend/core/schemas/local_auth.py`

**Step 1: Write the failing test**

Create `backend/tests/test_local_auth_schemas.py`:

```python
"""Test local auth Pydantic schemas for correct validation behavior."""
import uuid

import pytest
from pydantic import ValidationError


def test_local_user_create_schema() -> None:
    from core.schemas.local_auth import LocalUserCreate

    user = LocalUserCreate(username="alice", email="alice@blitz.local", password="strongpass123")
    assert user.username == "alice"
    assert user.email == "alice@blitz.local"
    assert user.password == "strongpass123"


def test_local_user_create_rejects_short_password() -> None:
    from core.schemas.local_auth import LocalUserCreate

    with pytest.raises(ValidationError):
        LocalUserCreate(username="alice", email="alice@blitz.local", password="short")


def test_local_user_response_excludes_password_hash() -> None:
    from core.schemas.local_auth import LocalUserResponse

    fields = LocalUserResponse.model_fields
    assert "password_hash" not in fields
    assert "password" not in fields
    assert "id" in fields
    assert "username" in fields
    assert "roles" in fields


def test_local_group_create_schema() -> None:
    from core.schemas.local_auth import LocalGroupCreate

    group = LocalGroupCreate(name="engineering", roles=["employee", "developer"])
    assert group.name == "engineering"
    assert group.roles == ["employee", "developer"]


def test_local_user_update_password_optional() -> None:
    from core.schemas.local_auth import LocalUserUpdate

    # Update without password change
    update = LocalUserUpdate(email="newemail@blitz.local")
    assert update.password is None
    assert update.email == "newemail@blitz.local"


def test_token_response_schema() -> None:
    from core.schemas.local_auth import TokenResponse

    resp = TokenResponse(access_token="abc.def.ghi", token_type="bearer")
    assert resp.access_token == "abc.def.ghi"
    assert resp.token_type == "bearer"
```

**Step 2: Run test to verify it fails**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_local_auth_schemas.py -v
```

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Create the schemas**

Create `backend/core/schemas/local_auth.py`:

```python
"""
Pydantic v2 schemas for local auth endpoints.

Request/response bodies for:
  - POST /auth/local/token (login)
  - CRUD /api/admin/local/users
  - CRUD /api/admin/local/groups
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ── Token ─────────────────────────────────────────────────────
class LocalLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Users ─────────────────────────────────────────────────────
class LocalUserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    group_ids: list[UUID] = Field(default_factory=list)
    direct_roles: list[str] = Field(default_factory=list)


class LocalUserUpdate(BaseModel):
    username: str | None = Field(None, min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8, max_length=128)
    is_active: bool | None = None


class LocalUserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    is_active: bool
    groups: list["LocalGroupBrief"] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LocalGroupBrief(BaseModel):
    id: UUID
    name: str


# ── Groups ────────────────────────────────────────────────────
class LocalGroupCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=64)
    description: str = Field(default="", max_length=500)
    roles: list[str] = Field(default_factory=list)


class LocalGroupUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=64)
    description: str | None = Field(None, max_length=500)
    roles: list[str] | None = None


class LocalGroupResponse(BaseModel):
    id: UUID
    name: str
    description: str
    roles: list[str] = Field(default_factory=list)
    member_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Role assignment ───────────────────────────────────────────
class RoleAssignment(BaseModel):
    roles: list[str] = Field(..., min_length=1)


class GroupAssignment(BaseModel):
    group_ids: list[UUID] = Field(..., min_length=1)


# Forward reference resolution
LocalUserResponse.model_rebuild()
```

**Step 4: Run test to verify it passes**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_local_auth_schemas.py -v
```

Expected: 6 passed

**Step 5: Commit**

```bash
git add backend/core/schemas/local_auth.py backend/tests/test_local_auth_schemas.py
git commit -m "feat(13-01): add Pydantic schemas for local auth endpoints"
```

---

### Task 6: Refactor validate_token() into Dual-Issuer Dispatch

**Files:**
- Modify: `backend/security/jwt.py:100-147` (validate_token function)
- Modify: `backend/tests/test_jwt.py` (add local JWT tests)

**Step 1: Write the failing test for local JWT validation**

Add to `backend/tests/test_jwt.py` at the end of the file:

```python
# ---------------------------------------------------------------------------
# Local auth JWT tests (HS256 + iss: "blitz-local")
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_local_jwt_valid_token() -> None:
    """A valid HS256 local JWT returns a fully populated UserContext."""
    import time
    from uuid import UUID

    from jose import jwt as jose_jwt

    from core.config import settings
    from security.jwt import validate_token

    user_id = str(uuid4())
    payload = {
        "sub": user_id,
        "iss": "blitz-local",
        "email": "local@blitz.local",
        "preferred_username": "localuser",
        "realm_roles": ["employee"],
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    token = jose_jwt.encode(payload, settings.local_jwt_secret, algorithm="HS256")

    ctx = await validate_token(token)
    assert ctx["email"] == "local@blitz.local"
    assert ctx["username"] == "localuser"
    assert "employee" in ctx["roles"]
    assert isinstance(ctx["user_id"], UUID)
    assert str(ctx["user_id"]) == user_id


@pytest.mark.asyncio
async def test_local_jwt_expired_raises_401() -> None:
    """An expired local HS256 JWT raises HTTPException 401."""
    import time

    from jose import jwt as jose_jwt

    from core.config import settings
    from security.jwt import validate_token

    payload = {
        "sub": str(uuid4()),
        "iss": "blitz-local",
        "email": "local@blitz.local",
        "preferred_username": "localuser",
        "realm_roles": ["employee"],
        "exp": int(time.time()) - 10,
        "iat": int(time.time()) - 3610,
    }
    token = jose_jwt.encode(payload, settings.local_jwt_secret, algorithm="HS256")

    with pytest.raises(HTTPException) as exc_info:
        await validate_token(token)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_local_jwt_wrong_secret_raises_401() -> None:
    """A local JWT signed with a different secret raises 401."""
    import time

    from jose import jwt as jose_jwt

    from security.jwt import validate_token

    payload = {
        "sub": str(uuid4()),
        "iss": "blitz-local",
        "email": "local@blitz.local",
        "preferred_username": "localuser",
        "realm_roles": ["employee"],
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    token = jose_jwt.encode(payload, "wrong-secret-not-the-real-one-xxxxx", algorithm="HS256")

    with pytest.raises(HTTPException) as exc_info:
        await validate_token(token)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_unknown_issuer_raises_401() -> None:
    """A JWT with an unrecognized issuer raises 401."""
    import time

    from jose import jwt as jose_jwt

    from core.config import settings
    from security.jwt import validate_token

    payload = {
        "sub": str(uuid4()),
        "iss": "https://evil.example.com",
        "email": "evil@example.com",
        "preferred_username": "evil",
        "realm_roles": ["employee"],
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    token = jose_jwt.encode(payload, settings.local_jwt_secret, algorithm="HS256")

    with pytest.raises(HTTPException) as exc_info:
        await validate_token(token)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_keycloak_jwt_still_works_after_refactor(make_token, mock_jwks) -> None:
    """After the dual-issuer refactor, existing Keycloak RS256 tokens still validate."""
    from security.jwt import validate_token

    token = make_token()

    with patch("security.jwt._get_jwks", new_callable=AsyncMock, return_value=mock_jwks):
        ctx = await validate_token(token)

    assert ctx["email"] == "test@blitz.local"
    assert "employee" in ctx["roles"]
```

**Step 2: Run tests to verify they fail**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_jwt.py::test_local_jwt_valid_token tests/test_jwt.py::test_unknown_issuer_raises_401 -v
```

Expected: FAIL (validate_token doesn't dispatch on issuer yet)

**Step 3: Refactor validate_token()**

Replace the `validate_token()` function in `backend/security/jwt.py` (lines 100-147) with:

```python
def _validate_local_token(token: str) -> UserContext:
    """
    Validate an HS256 JWT issued by the local auth system.

    Checks signature (HS256 + LOCAL_JWT_SECRET), expiry, and issuer.
    Returns the same UserContext as the Keycloak path.
    """
    try:
        payload: dict[str, Any] = jose_jwt.decode(
            token,
            settings.local_jwt_secret,
            algorithms=["HS256"],
            issuer="blitz-local",
        )
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError as exc:
        logger.warning("local_jwt_validation_failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=401, detail="Invalid token")

    roles: list[str] = payload.get("realm_roles", [])
    return UserContext(
        user_id=UUID(payload["sub"]),
        email=payload.get("email", ""),
        username=payload.get("preferred_username", ""),
        roles=roles,
        groups=payload.get("groups", []),
    )


async def _validate_keycloak_token(token: str) -> UserContext:
    """
    Validate an RS256 JWT issued by Keycloak.

    This is the original validate_token() body, extracted for the dual-issuer
    dispatch pattern. Checks RS256 signature against Keycloak JWKS, expiry,
    and issuer.
    """
    jwks = await _get_jwks()
    try:
        payload: dict[str, Any] = jose_jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            options={"verify_aud": False},
            issuer=settings.keycloak_issuer,
        )
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError as exc:
        logger.warning("jwt_validation_failed", error_type=type(exc).__name__, error=str(exc))
        raise HTTPException(status_code=401, detail="Invalid token")

    roles: list[str] = payload.get("realm_roles") or payload.get("realm_access", {}).get("roles", [])
    return UserContext(
        user_id=UUID(payload["sub"]),
        email=payload.get("email", ""),
        username=payload.get("preferred_username", ""),
        roles=roles,
        groups=payload.get("groups", []),
    )


async def validate_token(token: str) -> UserContext:
    """
    Validate a Bearer token — dual-issuer dispatch.

    Peeks at the unverified 'iss' claim to determine which validation path:
      - Keycloak issuer URL → RS256 + JWKS (existing path)
      - "blitz-local"       → HS256 + LOCAL_JWT_SECRET (new local auth)
      - Anything else       → 401

    Returns:
        UserContext populated from JWT claims.

    Raises:
        HTTPException(401) on any validation failure.
    """
    try:
        unverified = jose_jwt.get_unverified_claims(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    issuer = unverified.get("iss", "")

    if issuer == settings.keycloak_issuer:
        return await _validate_keycloak_token(token)
    elif issuer == "blitz-local":
        return _validate_local_token(token)
    else:
        logger.warning("unknown_token_issuer", issuer=issuer)
        raise HTTPException(status_code=401, detail="Invalid token")
```

**Step 4: Run all JWT tests to verify**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_jwt.py -v
```

Expected: All old tests pass + all new local JWT tests pass.

**Step 5: Run full test suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: No regressions.

**Step 6: Commit**

```bash
git add backend/security/jwt.py backend/tests/test_jwt.py
git commit -m "feat(13-01): refactor validate_token into dual-issuer dispatch (Keycloak RS256 + local HS256)"
```

---

### Task 7: Create POST /auth/local/token Endpoint

**Files:**
- Create: `backend/api/routes/auth_local.py`
- Modify: `backend/main.py` (register router)

**Step 1: Write the failing test**

Create `backend/tests/test_local_auth_login.py`:

```python
"""Test POST /auth/local/token — local user login endpoint."""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from passlib.hash import bcrypt


@pytest.fixture
def app() -> FastAPI:
    from api.routes.auth_local import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _make_mock_user(
    user_id=None, username="alice", email="alice@blitz.local", password="strongpass123", is_active=True
):
    """Create a mock LocalUser row."""
    mock = MagicMock()
    mock.id = user_id or uuid4()
    mock.username = username
    mock.email = email
    mock.password_hash = bcrypt.hash(password)
    mock.is_active = is_active
    return mock


def test_login_success(client: TestClient) -> None:
    """Valid credentials return a JWT access_token."""
    mock_user = _make_mock_user()

    # Mock the DB session and query
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    # Mock role resolution
    mock_roles_result = MagicMock()
    mock_roles_result.scalars.return_value.all.return_value = [MagicMock(role="employee")]
    mock_direct_result = MagicMock()
    mock_direct_result.scalars.return_value.all.return_value = []

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_result  # user lookup
        elif call_count == 2:
            return mock_roles_result  # group roles
        else:
            return mock_direct_result  # direct roles

    mock_session.execute = mock_execute

    with patch("api.routes.auth_local.async_session", return_value=mock_session):
        resp = client.post(
            "/auth/local/token",
            json={"username": "alice", "password": "strongpass123"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient) -> None:
    """Wrong password returns 401."""
    mock_user = _make_mock_user(password="strongpass123")

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("api.routes.auth_local.async_session", return_value=mock_session):
        resp = client.post(
            "/auth/local/token",
            json={"username": "alice", "password": "wrongpassword!"},
        )

    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


def test_login_nonexistent_user(client: TestClient) -> None:
    """Unknown username returns 401."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("api.routes.auth_local.async_session", return_value=mock_session):
        resp = client.post(
            "/auth/local/token",
            json={"username": "nobody", "password": "doesntmatter!"},
        )

    assert resp.status_code == 401


def test_login_inactive_user(client: TestClient) -> None:
    """Deactivated user returns 401."""
    mock_user = _make_mock_user(is_active=False)

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("api.routes.auth_local.async_session", return_value=mock_session):
        resp = client.post(
            "/auth/local/token",
            json={"username": "alice", "password": "strongpass123"},
        )

    assert resp.status_code == 401
```

**Step 2: Run test to verify it fails**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_local_auth_login.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'api.routes.auth_local'`

**Step 3: Create the login endpoint**

Create `backend/api/routes/auth_local.py`:

```python
"""
Local auth login endpoint — POST /auth/local/token.

Authenticates a local user by username/password and returns an HS256 JWT
with the same claim structure as Keycloak JWTs (sub, iss, email,
preferred_username, realm_roles). No auth required on this endpoint
— it IS the authentication entry point.

Security:
  - Passwords verified via bcrypt (passlib)
  - Timing-safe comparison (bcrypt handles this internally)
  - Inactive users rejected
  - Credentials never logged
"""
import time

import structlog
from fastapi import APIRouter, HTTPException
from jose import jwt as jose_jwt
from passlib.hash import bcrypt
from sqlalchemy import select

from core.config import settings
from core.db import async_session
from core.models.local_auth import (
    LocalGroupRole,
    LocalUser,
    LocalUserGroup,
    LocalUserRole,
)
from core.schemas.local_auth import LocalLoginRequest, TokenResponse

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["local-auth"])


async def _resolve_roles(session, user_id) -> list[str]:
    """Compute effective roles = group roles ∪ direct roles."""
    # Group roles: user_groups JOIN group_roles
    group_roles_result = await session.execute(
        select(LocalGroupRole.role)
        .join(LocalUserGroup, LocalGroupRole.group_id == LocalUserGroup.group_id)
        .where(LocalUserGroup.user_id == user_id)
    )
    group_roles = {r for r in group_roles_result.scalars().all()}

    # Direct user roles
    direct_roles_result = await session.execute(
        select(LocalUserRole.role).where(LocalUserRole.user_id == user_id)
    )
    direct_roles = {r for r in direct_roles_result.scalars().all()}

    return sorted(group_roles | direct_roles)


def _issue_local_jwt(user_id: str, email: str, username: str, roles: list[str]) -> str:
    """Sign an HS256 JWT with the local auth secret."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "iss": "blitz-local",
        "iat": now,
        "exp": now + (settings.local_jwt_expires_hours * 3600),
        "email": email,
        "preferred_username": username,
        "realm_roles": roles,
    }
    return jose_jwt.encode(payload, settings.local_jwt_secret, algorithm="HS256")


@router.post("/auth/local/token", response_model=TokenResponse)
async def local_login(body: LocalLoginRequest) -> TokenResponse:
    """
    Authenticate a local user and return an HS256 JWT.

    The returned token has the same claim structure as Keycloak JWTs,
    so it passes through the existing 3-gate security system identically.
    """
    async with async_session() as session:
        # Fetch user by username
        result = await session.execute(
            select(LocalUser).where(LocalUser.username == body.username)
        )
        user = result.scalar_one_or_none()

        if user is None:
            logger.info("local_login_failed", reason="user_not_found", username=body.username)
            raise HTTPException(status_code=401, detail="Invalid username or password")

        if not user.is_active:
            logger.info("local_login_failed", reason="inactive", username=body.username)
            raise HTTPException(status_code=401, detail="Invalid username or password")

        if not bcrypt.verify(body.password, user.password_hash):
            logger.info("local_login_failed", reason="wrong_password", username=body.username)
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # Resolve effective roles
        roles = await _resolve_roles(session, user.id)

        # Issue JWT
        token = _issue_local_jwt(
            user_id=str(user.id),
            email=user.email,
            username=user.username,
            roles=roles,
        )

        logger.info("local_login_success", username=body.username, user_id=str(user.id))
        return TokenResponse(access_token=token)
```

**Step 4: Register router in main.py**

Add to `backend/main.py` imports:

```python
from api.routes.auth_local import router as auth_local_router
```

And in `create_app()` before the health router:

```python
    # Local auth login — POST /auth/local/token (no JWT required)
    app.include_router(auth_local_router)
```

**Step 5: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_local_auth_login.py -v
```

Expected: 4 passed

**Step 6: Run full test suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

**Step 7: Commit**

```bash
git add backend/api/routes/auth_local.py backend/main.py backend/tests/test_local_auth_login.py
git commit -m "feat(13-01): add POST /auth/local/token login endpoint with bcrypt + HS256 JWT"
```

---

### Task 8: Create Admin CRUD Routes for Local Users and Groups

**Files:**
- Create: `backend/api/routes/admin_local_users.py`
- Modify: `backend/main.py` (register router)

**Step 1: Write the failing test**

Create `backend/tests/api/test_admin_local_users.py`:

```python
"""Test admin CRUD routes for local users and groups."""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from passlib.hash import bcrypt


def _admin_user():
    return {
        "user_id": uuid4(),
        "email": "admin@blitz.local",
        "username": "admin",
        "roles": ["it-admin"],
        "groups": [],
    }


def _employee_user():
    return {
        "user_id": uuid4(),
        "email": "emp@blitz.local",
        "username": "emp",
        "roles": ["employee"],
        "groups": [],
    }


@pytest.fixture
def app() -> FastAPI:
    from api.routes.admin_local_users import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def admin_client(app: FastAPI) -> TestClient:
    from security.deps import get_current_user

    app.dependency_overrides[get_current_user] = lambda: _admin_user()
    return TestClient(app)


@pytest.fixture
def employee_client(app: FastAPI) -> TestClient:
    from security.deps import get_current_user

    app.dependency_overrides[get_current_user] = lambda: _employee_user()
    return TestClient(app)


def test_create_user_requires_admin(employee_client: TestClient) -> None:
    """Non-admin user gets 403 on user creation."""
    with patch("api.routes.admin_local_users.get_db") as mock_db:
        mock_session = AsyncMock()
        mock_db.return_value = mock_session
        resp = employee_client.post(
            "/api/admin/local/users",
            json={
                "username": "newuser",
                "email": "new@blitz.local",
                "password": "strongpass123",
            },
        )
    assert resp.status_code == 403


def test_list_users_returns_empty(admin_client: TestClient) -> None:
    """Admin can list local users (empty result)."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("api.routes.admin_local_users.get_db", return_value=mock_session):
        with patch("security.rbac.has_permission", return_value=True):
            resp = admin_client.get("/api/admin/local/users")

    assert resp.status_code == 200
    assert resp.json() == []


def test_list_groups_returns_empty(admin_client: TestClient) -> None:
    """Admin can list local groups (empty result)."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("api.routes.admin_local_users.get_db", return_value=mock_session):
        with patch("security.rbac.has_permission", return_value=True):
            resp = admin_client.get("/api/admin/local/groups")

    assert resp.status_code == 200
    assert resp.json() == []
```

**Step 2: Run test to verify it fails**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/api/test_admin_local_users.py -v
```

Expected: FAIL

**Step 3: Create the admin CRUD routes**

Create `backend/api/routes/admin_local_users.py`:

```python
"""
Admin CRUD API for local users and groups.

All endpoints require `registry:manage` permission (Gate 2 RBAC).
Passwords are bcrypt-hashed on create/update; password_hash never returned.

Routes:
  POST   /api/admin/local/users              — create user
  GET    /api/admin/local/users              — list users
  GET    /api/admin/local/users/{id}         — get user detail
  PUT    /api/admin/local/users/{id}         — update user
  DELETE /api/admin/local/users/{id}         — delete user
  POST   /api/admin/local/users/{id}/groups  — assign groups
  DELETE /api/admin/local/users/{id}/groups/{gid} — remove from group
  POST   /api/admin/local/users/{id}/roles   — add direct roles
  DELETE /api/admin/local/users/{id}/roles/{role} — remove direct role

  POST   /api/admin/local/groups             — create group
  GET    /api/admin/local/groups             — list groups
  PUT    /api/admin/local/groups/{id}        — update group
  DELETE /api/admin/local/groups/{id}        — delete group
"""
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from passlib.hash import bcrypt
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.local_auth import (
    LocalGroup,
    LocalGroupRole,
    LocalUser,
    LocalUserGroup,
    LocalUserRole,
)
from core.models.user import UserContext
from core.schemas.local_auth import (
    GroupAssignment,
    LocalGroupBrief,
    LocalGroupCreate,
    LocalGroupResponse,
    LocalGroupUpdate,
    LocalUserCreate,
    LocalUserResponse,
    LocalUserUpdate,
    RoleAssignment,
)
from security.deps import get_current_user
from security.rbac import has_permission

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin/local", tags=["admin-local-auth"])


async def _require_registry_manager(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2 dependency: require registry:manage permission."""
    if not await has_permission(user, "registry:manage", session):
        raise HTTPException(status_code=403, detail="Registry manage permission required")
    return user


async def _resolve_user_roles(session: AsyncSession, user_id: UUID) -> list[str]:
    """Compute effective roles = group roles ∪ direct roles."""
    group_roles_result = await session.execute(
        select(LocalGroupRole.role)
        .join(LocalUserGroup, LocalGroupRole.group_id == LocalUserGroup.group_id)
        .where(LocalUserGroup.user_id == user_id)
    )
    group_roles = set(group_roles_result.scalars().all())

    direct_roles_result = await session.execute(
        select(LocalUserRole.role).where(LocalUserRole.user_id == user_id)
    )
    direct_roles = set(direct_roles_result.scalars().all())

    return sorted(group_roles | direct_roles)


async def _resolve_user_groups(session: AsyncSession, user_id: UUID) -> list[LocalGroupBrief]:
    """Get all groups a user belongs to."""
    result = await session.execute(
        select(LocalGroup)
        .join(LocalUserGroup, LocalGroup.id == LocalUserGroup.group_id)
        .where(LocalUserGroup.user_id == user_id)
    )
    return [LocalGroupBrief(id=g.id, name=g.name) for g in result.scalars().all()]


async def _user_to_response(session: AsyncSession, user: LocalUser) -> LocalUserResponse:
    """Convert a LocalUser ORM object to a response schema with resolved roles and groups."""
    roles = await _resolve_user_roles(session, user.id)
    groups = await _resolve_user_groups(session, user.id)
    return LocalUserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        groups=groups,
        roles=roles,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


# ── User endpoints ────────────────────────────────────────────


@router.post("/users", response_model=LocalUserResponse, status_code=201)
async def create_user(
    body: LocalUserCreate,
    _admin: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> LocalUserResponse:
    """Create a new local user account."""
    # Check username uniqueness
    existing = await session.execute(
        select(LocalUser).where(LocalUser.username == body.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already taken")

    # Check email uniqueness
    existing_email = await session.execute(
        select(LocalUser).where(LocalUser.email == body.email)
    )
    if existing_email.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already taken")

    user = LocalUser(
        username=body.username,
        email=body.email,
        password_hash=bcrypt.hash(body.password),
    )
    session.add(user)
    await session.flush()

    # Assign groups
    for gid in body.group_ids:
        session.add(LocalUserGroup(user_id=user.id, group_id=gid))

    # Assign direct roles
    for role in body.direct_roles:
        session.add(LocalUserRole(user_id=user.id, role=role))

    await session.commit()
    await session.refresh(user)

    logger.info("local_user_created", username=user.username, user_id=str(user.id))
    return await _user_to_response(session, user)


@router.get("/users", response_model=list[LocalUserResponse])
async def list_users(
    _admin: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> list[LocalUserResponse]:
    """List all local user accounts."""
    result = await session.execute(select(LocalUser).order_by(LocalUser.username))
    users = result.scalars().all()
    return [await _user_to_response(session, u) for u in users]


@router.get("/users/{user_id}", response_model=LocalUserResponse)
async def get_user(
    user_id: UUID,
    _admin: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> LocalUserResponse:
    """Get a single local user by ID."""
    result = await session.execute(select(LocalUser).where(LocalUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return await _user_to_response(session, user)


@router.put("/users/{user_id}", response_model=LocalUserResponse)
async def update_user(
    user_id: UUID,
    body: LocalUserUpdate,
    _admin: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> LocalUserResponse:
    """Update a local user. Password is optional (only changed if provided)."""
    result = await session.execute(select(LocalUser).where(LocalUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.username is not None:
        # Check uniqueness
        dup = await session.execute(
            select(LocalUser).where(LocalUser.username == body.username, LocalUser.id != user_id)
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Username already taken")
        user.username = body.username

    if body.email is not None:
        dup = await session.execute(
            select(LocalUser).where(LocalUser.email == body.email, LocalUser.id != user_id)
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email already taken")
        user.email = body.email

    if body.password is not None:
        user.password_hash = bcrypt.hash(body.password)

    if body.is_active is not None:
        user.is_active = body.is_active

    await session.commit()
    await session.refresh(user)
    return await _user_to_response(session, user)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: UUID,
    _admin: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a local user account."""
    result = await session.execute(select(LocalUser).where(LocalUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await session.delete(user)
    await session.commit()
    logger.info("local_user_deleted", username=user.username, user_id=str(user_id))


@router.post("/users/{user_id}/groups", status_code=204)
async def assign_groups(
    user_id: UUID,
    body: GroupAssignment,
    _admin: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Assign groups to a user."""
    for gid in body.group_ids:
        session.add(LocalUserGroup(user_id=user_id, group_id=gid))
    await session.commit()


@router.delete("/users/{user_id}/groups/{group_id}", status_code=204)
async def remove_group(
    user_id: UUID,
    group_id: UUID,
    _admin: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Remove a user from a group."""
    await session.execute(
        delete(LocalUserGroup).where(
            LocalUserGroup.user_id == user_id,
            LocalUserGroup.group_id == group_id,
        )
    )
    await session.commit()


@router.post("/users/{user_id}/roles", status_code=204)
async def add_direct_roles(
    user_id: UUID,
    body: RoleAssignment,
    _admin: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Add direct role assignments to a user."""
    for role in body.roles:
        session.add(LocalUserRole(user_id=user_id, role=role))
    await session.commit()


@router.delete("/users/{user_id}/roles/{role}", status_code=204)
async def remove_direct_role(
    user_id: UUID,
    role: str,
    _admin: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Remove a direct role from a user."""
    await session.execute(
        delete(LocalUserRole).where(
            LocalUserRole.user_id == user_id,
            LocalUserRole.role == role,
        )
    )
    await session.commit()


# ── Group endpoints ───────────────────────────────────────────


@router.post("/groups", response_model=LocalGroupResponse, status_code=201)
async def create_group(
    body: LocalGroupCreate,
    _admin: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> LocalGroupResponse:
    """Create a new local group."""
    existing = await session.execute(
        select(LocalGroup).where(LocalGroup.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Group name already taken")

    group = LocalGroup(name=body.name, description=body.description)
    session.add(group)
    await session.flush()

    for role in body.roles:
        session.add(LocalGroupRole(group_id=group.id, role=role))

    await session.commit()
    await session.refresh(group)

    return LocalGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        roles=body.roles,
        member_count=0,
        created_at=group.created_at,
    )


@router.get("/groups", response_model=list[LocalGroupResponse])
async def list_groups(
    _admin: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> list[LocalGroupResponse]:
    """List all local groups."""
    result = await session.execute(select(LocalGroup).order_by(LocalGroup.name))
    groups = result.scalars().all()

    responses = []
    for g in groups:
        roles_result = await session.execute(
            select(LocalGroupRole.role).where(LocalGroupRole.group_id == g.id)
        )
        roles = list(roles_result.scalars().all())

        count_result = await session.execute(
            select(func.count()).select_from(LocalUserGroup).where(LocalUserGroup.group_id == g.id)
        )
        member_count = count_result.scalar() or 0

        responses.append(LocalGroupResponse(
            id=g.id,
            name=g.name,
            description=g.description,
            roles=roles,
            member_count=member_count,
            created_at=g.created_at,
        ))
    return responses


@router.put("/groups/{group_id}", response_model=LocalGroupResponse)
async def update_group(
    group_id: UUID,
    body: LocalGroupUpdate,
    _admin: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> LocalGroupResponse:
    """Update a local group (name, description, roles)."""
    result = await session.execute(select(LocalGroup).where(LocalGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if body.name is not None:
        dup = await session.execute(
            select(LocalGroup).where(LocalGroup.name == body.name, LocalGroup.id != group_id)
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Group name already taken")
        group.name = body.name

    if body.description is not None:
        group.description = body.description

    if body.roles is not None:
        # Replace all group roles
        await session.execute(
            delete(LocalGroupRole).where(LocalGroupRole.group_id == group_id)
        )
        for role in body.roles:
            session.add(LocalGroupRole(group_id=group_id, role=role))

    await session.commit()
    await session.refresh(group)

    roles_result = await session.execute(
        select(LocalGroupRole.role).where(LocalGroupRole.group_id == group.id)
    )
    roles = list(roles_result.scalars().all())

    count_result = await session.execute(
        select(func.count()).select_from(LocalUserGroup).where(LocalUserGroup.group_id == group.id)
    )
    member_count = count_result.scalar() or 0

    return LocalGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        roles=roles,
        member_count=member_count,
        created_at=group.created_at,
    )


@router.delete("/groups/{group_id}", status_code=204)
async def delete_group(
    group_id: UUID,
    _admin: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a local group (cascades to user_groups and group_roles)."""
    result = await session.execute(select(LocalGroup).where(LocalGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    await session.delete(group)
    await session.commit()
    logger.info("local_group_deleted", name=group.name, group_id=str(group_id))
```

**Step 4: Register router in main.py**

Add to `backend/main.py` imports:

```python
from api.routes.admin_local_users import router as admin_local_users_router
```

And in `create_app()`:

```python
    # Admin local user/group management — /api/admin/local/* (registry:manage permission)
    app.include_router(admin_local_users_router)
```

**Step 5: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/api/test_admin_local_users.py -v
```

Expected: 3 passed

**Step 6: Run full suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

**Step 7: Commit**

```bash
git add backend/api/routes/admin_local_users.py backend/main.py backend/tests/api/test_admin_local_users.py
git commit -m "feat(13-01): add admin CRUD routes for local users and groups"
```

---

### Task 9: Update dev-context.md with New Endpoints

**Files:**
- Modify: `docs/dev-context.md`

**Step 1: Add local auth endpoints to Section 2**

Add a new subsection under `## 2. Backend API Endpoints`:

```markdown
### Local Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/local/token` | Local username/password login (no JWT required) |

### Admin — Local User Management (Phase 13)

All endpoints require `registry:manage` permission (Gate 2 RBAC — it-admin role).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/admin/local/users` | Create local user |
| GET | `/api/admin/local/users` | List local users |
| GET | `/api/admin/local/users/{id}` | Get user detail |
| PUT | `/api/admin/local/users/{id}` | Update user (password optional) |
| DELETE | `/api/admin/local/users/{id}` | Delete user |
| POST | `/api/admin/local/users/{id}/groups` | Assign groups |
| DELETE | `/api/admin/local/users/{id}/groups/{gid}` | Remove from group |
| POST | `/api/admin/local/users/{id}/roles` | Add direct roles |
| DELETE | `/api/admin/local/users/{id}/roles/{role}` | Remove direct role |
| POST | `/api/admin/local/groups` | Create group |
| GET | `/api/admin/local/groups` | List groups |
| PUT | `/api/admin/local/groups/{id}` | Update group |
| DELETE | `/api/admin/local/groups/{id}` | Delete group |
```

Also add to Section 5 (Database) Key Tables:

```markdown
| `local_users` | Local user accounts (parallel to Keycloak) |
| `local_groups` | Named groups with role assignments |
| `local_user_groups` | User ↔ Group membership (M2M) |
| `local_group_roles` | Group → Role assignments (M2M) |
| `local_user_roles` | Direct user → Role overrides |
```

Add to Section 9 (Update Log):

```markdown
| 2026-03-03 | [Phase 13]: Local auth endpoints, 5 new tables, dual-issuer JWT (iss dispatch) | claude |
```

**Step 2: Commit**

```bash
git add docs/dev-context.md
git commit -m "docs(13-01): update dev-context.md with local auth endpoints and tables"
```

---

### Task 10: Final Verification

**Step 1: Run full backend test suite**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: All tests pass (previous baseline + new local auth tests).

**Step 2: Check no type errors (if mypy/pyright configured)**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/python -c "
from api.routes.auth_local import router as r1
from api.routes.admin_local_users import router as r2
from security.jwt import validate_token
from core.models.local_auth import LocalUser, LocalGroup
from core.schemas.local_auth import LocalUserCreate, LocalGroupCreate, TokenResponse
print('All imports OK')
"
```

Expected: `All imports OK`

**Step 3: Verify commit log**

```bash
git log --oneline -8
```

Expected: 7-8 commits with `feat(13-01)` or `docs(13-01)` prefix.
