# Projects & Spaces Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build organizational workspaces and NotebookLM-like personal projects with team collaboration, semantic search, and AI insights.

**Architecture:** Unified Project Model (Approach A) - Single `projects` table with nullable `workspace_id`. Personal projects have `workspace_id = NULL`, workspace projects reference a workspace. Sharing personal projects to workspaces via `project_permissions` table. pgvector for semantic search (bge-m3, 1024-dim). Celery for async embeddings, insights, backups.

**Tech Stack:**
- Backend: FastAPI 0.115+, SQLAlchemy async, PostgreSQL 16+ with pgvector
- Frontend: Next.js 15+, React, TypeScript
- Embedding: bge-m3 (BAAI) via FlagEmbedding
- Task Queue: Celery 5+ with Redis broker
- LLM: LiteLLM Proxy (blitz/master alias)

---

## Phase 1: Foundation (Week 1-2)

### Task 1: Create Database Migration for Core Tables

**Files:**
- Create: `backend/alembic/versions/040_add_projects_spaces.py`

**Step 1: Write migration script**

```python
"""add projects and spaces tables

Revision ID: 040
Revises: 039 (or latest head)
Create Date: 2026-03-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '040_add_projects_spaces'
down_revision = '039_registry_entries'  # Adjust to latest
branch_labels = None
depends_on = None


def upgrade():
    # Workspaces table
    op.create_table(
        'workspaces',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default='active'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("status IN ('active', 'archived')", name='ck_workspaces_status')
    )
    op.create_index('idx_workspaces_created_by', 'workspaces', ['created_by'])
    op.create_index('idx_workspaces_status', 'workspaces', ['status'])

    # Workspace members table
    op.create_table(
        'workspace_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('grantee_type', sa.Text(), nullable=False),
        sa.Column('grantee_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('added_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("grantee_type IN ('user', 'group')", name='ck_workspace_members_grantee_type'),
        sa.CheckConstraint("role IN ('admin', 'member')", name='ck_workspace_members_role'),
        sa.UniqueConstraint('workspace_id', 'grantee_type', 'grantee_id', name='uq_workspace_member')
    )
    op.create_index('idx_workspace_members_workspace', 'workspace_members', ['workspace_id'])
    op.create_index('idx_workspace_members_grantee', 'workspace_members', ['grantee_type', 'grantee_id'])
    op.create_foreign_key('fk_workspace_members_workspace', 'workspace_members', 'workspaces', ['workspace_id'], ['id'], ondelete='CASCADE')

    # Projects table
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('status', sa.Text(), nullable=False, server_default='active'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("status IN ('active', 'archived')", name='ck_projects_status')
    )
    op.create_index('idx_projects_owner', 'projects', ['owner_id'])
    op.create_index('idx_projects_workspace', 'projects', ['workspace_id'])
    op.create_index('idx_projects_status', 'projects', ['status'])
    op.create_index('idx_projects_public', 'projects', ['is_public'], postgresql_where=sa.text('is_public = TRUE'))

    # Project permissions table
    op.create_table(
        'project_permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('grantee_type', sa.Text(), nullable=False),
        sa.Column('grantee_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('granted_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("grantee_type IN ('user', 'group', 'workspace')", name='ck_project_permissions_grantee_type'),
        sa.CheckConstraint("role IN ('view', 'edit', 'full')", name='ck_project_permissions_role'),
        sa.UniqueConstraint('project_id', 'grantee_type', 'grantee_id', name='uq_project_permission')
    )
    op.create_index('idx_project_permissions_project', 'project_permissions', ['project_id'])
    op.create_index('idx_project_permissions_grantee', 'project_permissions', ['grantee_type', 'grantee_id'])
    op.create_foreign_key('fk_project_permissions_project', 'project_permissions', 'projects', ['project_id'], ['id'], ondelete='CASCADE')


def downgrade():
    op.drop_table('project_permissions')
    op.drop_table('projects')
    op.drop_table('workspace_members')
    op.drop_table('workspaces')
```

**Step 2: Run migration to verify it applies**

Run: `docker exec -it blitz-backend .venv/bin/alembic upgrade head`
Expected: Migration applies successfully, tables created

**Step 3: Verify tables in database**

Run: `docker exec -it blitz-postgres psql -U blitz blitz -c "\dt workspaces; \dt workspace_members; \dt projects; \dt project_permissions;"`
Expected: All 4 tables exist with correct columns

**Step 4: Commit**

```bash
git add backend/alembic/versions/040_add_projects_spaces.py
git commit -m "feat(20-01): add projects and spaces core tables migration"
```

---

### Task 2: Create SQLAlchemy Models

**Files:**
- Create: `backend/core/models/workspace.py`
- Create: `backend/core/models/project.py`
- Modify: `backend/core/models/__init__.py`

**Step 1: Write workspace models**

```python
# backend/core/models/workspace.py
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from .base import Base

if TYPE_CHECKING:
    from .user import User


class Workspace(Base):
    __tablename__ = 'workspaces'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    status = Column(String, nullable=False, default='active', server_default='active')
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    members = relationship('WorkspaceMember', back_populates='workspace', cascade='all, delete-orphan')
    projects = relationship('Project', back_populates='workspace', cascade='all, delete-orphan')

    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name='ck_workspaces_status'),
        Index('idx_workspaces_created_by', 'created_by'),
        Index('idx_workspaces_status', 'status')
    )


class WorkspaceMember(Base):
    __tablename__ = 'workspace_members'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False)
    grantee_type = Column(String, nullable=False)
    grantee_id = Column(UUID(as_uuid=True), nullable=False)
    role = Column(String, nullable=False)
    added_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    workspace = relationship('Workspace', back_populates='members')

    __table_args__ = (
        CheckConstraint("grantee_type IN ('user', 'group')", name='ck_workspace_members_grantee_type'),
        CheckConstraint("role IN ('admin', 'member')", name='ck_workspace_members_role'),
        UniqueConstraint('workspace_id', 'grantee_type', 'grantee_id', name='uq_workspace_member'),
        Index('idx_workspace_members_workspace', 'workspace_id'),
        Index('idx_workspace_members_grantee', 'grantee_type', 'grantee_id')
    )
```

**Step 2: Write project models**

```python
# backend/core/models/project.py
from datetime import datetime
from typing import TYPE_CHECKING, List
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
import uuid

from .base import Base

if TYPE_CHECKING:
    from .user import User
    from .workspace import Workspace


class Project(Base):
    __tablename__ = 'projects'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.id', ondelete='SET NULL'), nullable=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, nullable=False, default=False, server_default='false')
    status = Column(String, nullable=False, default='active', server_default='active')
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    owner = relationship('User', foreign_keys=[owner_id])
    workspace = relationship('Workspace', back_populates='projects', foreign_keys=[workspace_id])
    permissions = relationship('ProjectPermission', back_populates='project', cascade='all, delete-orphan')
    sections = relationship('ProjectSection', back_populates='project', cascade='all, delete-orphan')
    sources = relationship('ProjectSource', back_populates='project', cascade='all, delete-orphan')
    chats = relationship('ProjectChat', back_populates='project', cascade='all, delete-orphan')
    insights = relationship('ProjectInsight', back_populates='project', cascade='all, delete-orphan')
    backups = relationship('ProjectBackup', back_populates='project')

    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name='ck_projects_status'),
        Index('idx_projects_owner', 'owner_id'),
        Index('idx_projects_workspace', 'workspace_id'),
        Index('idx_projects_status', 'status'),
        Index('idx_projects_public', 'is_public', postgresql_where=is_public == True)
    )

    @hybrid_property
    def is_personal(self) -> bool:
        return self.workspace_id is None


class ProjectPermission(Base):
    __tablename__ = 'project_permissions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    grantee_type = Column(String, nullable=False)
    grantee_id = Column(UUID(as_uuid=True), nullable=False)
    role = Column(String, nullable=False)
    granted_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    project = relationship('Project', back_populates='permissions')

    __table_args__ = (
        CheckConstraint("grantee_type IN ('user', 'group', 'workspace')", name='ck_project_permissions_grantee_type'),
        CheckConstraint("role IN ('view', 'edit', 'full')", name='ck_project_permissions_role'),
        UniqueConstraint('project_id', 'grantee_type', 'grantee_id', name='uq_project_permission'),
        Index('idx_project_permissions_project', 'project_id'),
        Index('idx_project_permissions_grantee', 'grantee_type', 'grantee_id')
    )
```

**Step 3: Register models in __init__.py**

```python
# backend/core/models/__init__.py (add imports)
from .workspace import Workspace, WorkspaceMember
from .project import Project, ProjectPermission

__all__ = [
    # ... existing imports
    'Workspace',
    'WorkspaceMember',
    'Project',
    'ProjectPermission',
]
```

**Step 4: Write failing test for model creation**

```python
# tests/models/test_workspace.py
import pytest
from core.models.workspace import Workspace, WorkspaceMember
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_create_workspace(db_session: AsyncSession):
    workspace = Workspace(
        name="Test Workspace",
        description="A test workspace",
        created_by=uuid.uuid4()
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    assert workspace.id is not None
    assert workspace.name == "Test Workspace"
    assert workspace.status == "active"


@pytest.mark.asyncio
async def test_workspace_member_unique_constraint(db_session: AsyncSession):
    """Verify that same user cannot be added twice to workspace"""
    workspace = Workspace(name="Test", created_by=uuid.uuid4())
    db_session.add(workspace)
    await db_session.commit()

    user_id = uuid.uuid4()
    member1 = WorkspaceMember(
        workspace_id=workspace.id,
        grantee_type="user",
        grantee_id=user_id,
        role="member",
        added_by=workspace.created_by
    )
    db_session.add(member1)
    await db_session.commit()

    # Try to add same user again
    member2 = WorkspaceMember(
        workspace_id=workspace.id,
        grantee_type="user",
        grantee_id=user_id,
        role="admin",
        added_by=workspace.created_by
    )
    db_session.add(member2)

    with pytest.raises(Exception):  # Should raise IntegrityError
        await db_session.commit()
```

**Step 5: Run test to verify it fails (models not yet imported)**

Run: `PYTHONPATH=. .venv/bin/pytest tests/models/test_workspace.py::test_create_workspace -v`
Expected: FAIL with "Workspace not found" (models not registered)

**Step 6: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/models/test_workspace.py::test_create_workspace -v`
Expected: PASS

**Step 7: Commit**

```bash
git add backend/core/models/workspace.py backend/core/models/project.py backend/core/models/__init__.py
git commit -m "feat(20-01): add workspace and project SQLAlchemy models"
```

---

### Task 3: Create Pydantic Schemas

**Files:**
- Create: `backend/core/schemas/workspace.py`
- Create: `backend/core/schemas/project.py`

**Step 1: Write workspace schemas**

```python
# backend/core/schemas/workspace.py
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field
import uuid


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None


class WorkspaceUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class WorkspaceMemberCreate(BaseModel):
    grantee_type: Literal['user', 'group'] = Field(...)
    grantee_id: uuid.UUID = Field(...)
    role: Literal['admin', 'member'] = Field(...)


class WorkspaceMemberResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    grantee_type: str
    grantee_id: uuid.UUID
    role: str
    added_by: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    created_by: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkspaceListResponse(WorkspaceResponse):
    member_count: Optional[int] = 0
    project_count: Optional[int] = 0
```

**Step 2: Write project schemas**

```python
# backend/core/schemas/project.py
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field
import uuid


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    workspace_id: Optional[uuid.UUID] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None


class ProjectPublicToggle(BaseModel):
    is_public: bool


class ProjectPermissionCreate(BaseModel):
    grantee_type: Literal['user', 'group', 'workspace'] = Field(...)
    grantee_id: uuid.UUID = Field(...)
    role: Literal['view', 'edit', 'full'] = Field(...)


class ProjectPermissionResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    grantee_type: str
    grantee_id: uuid.UUID
    role: str
    granted_by: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    workspace_id: Optional[uuid.UUID]
    name: str
    description: Optional[str]
    is_public: bool
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectListResponse(ProjectResponse):
    owner_name: Optional[str] = None
    member_role: Optional[str] = None
```

**Step 3: Write failing test for schema validation**

```python
# tests/schemas/test_workspace.py
import pytest
from core.schemas.workspace import WorkspaceCreate, WorkspaceMemberCreate


def test_workspace_create_validation():
    """Valid workspace create request"""
    data = {"name": "My Workspace", "description": "A test workspace"}
    workspace = WorkspaceCreate(**data)
    assert workspace.name == "My Workspace"
    assert workspace.description == "A test workspace"


def test_workspace_create_empty_name_fails():
    """Empty name should fail validation"""
    with pytest.raises(ValueError):
        WorkspaceCreate(name="", description="Test")


def test_workspace_member_invalid_grantee_type():
    """Invalid grantee_type should fail validation"""
    with pytest.raises(ValueError):
        WorkspaceMemberCreate(grantee_type="invalid", grantee_id=uuid.uuid4(), role="member")
```

**Step 4: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/schemas/test_workspace.py -v`
Expected: FAIL (tests not written yet)

**Step 5: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/schemas/test_workspace.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/core/schemas/workspace.py backend/core/schemas/project.py
git commit -m "feat(20-01): add workspace and project Pydantic schemas"
```

---

### Task 4: Create Permission Service

**Files:**
- Create: `backend/services/permission_service.py`

**Step 1: Write permission service with role hierarchy**

```python
# backend/services/permission_service.py
from typing import Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from core.models.project import Project, ProjectPermission
from core.models.workspace import Workspace, WorkspaceMember
from core.models.user import User, UserGroup


class PermissionService:
    """Service for checking project and workspace permissions"""

    ROLE_HIERARCHY = {'view': 1, 'edit': 2, 'full': 3}

    @staticmethod
    def role_sufficient(have: str, need: str) -> bool:
        """Check if 'have' role satisfies 'need' role"""
        return PermissionService.ROLE_HIERARCHY.get(have, 0) >= PermissionService.ROLE_HIERARCHY.get(need, 0)

    @staticmethod
    async def check_project_access(
        db: AsyncSession,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        required_role: str = 'view'
    ) -> bool:
        """
        Check if user has required role on project.

        Returns True if:
        - User is owner (always full access)
        - Project is workspace project AND (is_public OR user has permission)
        - User has explicit permission (shared personal project or workspace grant)
        """
        project = await db.get(Project, project_id)
        if not project:
            return False

        # Owner check
        if project.owner_id == user_id:
            return True

        # Workspace project: check public OR permission
        if project.workspace_id is not None:
            if project.is_public:
                return True

            # Check workspace membership + permission
            workspace_member = await db.execute(
                select(WorkspaceMember).where(
                    and_(
                        WorkspaceMember.workspace_id == project.workspace_id,
                        WorkspaceMember.grantee_type == 'user',
                        WorkspaceMember.grantee_id == user_id
                    )
                )
            )
            workspace_member = workspace_member.scalar_one_or_none()
            if workspace_member:
                return await PermissionService._has_permission_role(db, project_id, user_id, required_role)

        # Personal project shared to user (or workspace user is in)
        return await PermissionService._has_permission_role(db, project_id, user_id, required_role)

    @staticmethod
    async def _has_permission_role(
        db: AsyncSession,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        required_role: str
    ) -> bool:
        """Check if user has sufficient permission via direct or indirect grants"""

        # Check direct user permission
        user_perm = await db.execute(
            select(ProjectPermission).where(
                and_(
                    ProjectPermission.project_id == project_id,
                    ProjectPermission.grantee_type == 'user',
                    ProjectPermission.grantee_id == user_id
                )
            )
        )
        user_perm = user_perm.scalar_one_or_none()
        if user_perm and PermissionService.role_sufficient(user_perm.role, required_role):
            return True

        # Check group permissions
        user_groups = await db.execute(
            select(UserGroup.group_id).where(UserGroup.user_id == user_id)
        )
        user_groups = user_groups.scalars().all()
        for group_id in user_groups:
            group_perm = await db.execute(
                select(ProjectPermission).where(
                    and_(
                        ProjectPermission.project_id == project_id,
                        ProjectPermission.grantee_type == 'group',
                        ProjectPermission.grantee_id == group_id
                    )
                )
            )
            group_perm = group_perm.scalar_one_or_none()
            if group_perm and PermissionService.role_sufficient(group_perm.role, required_role):
                return True

        # Check workspace permissions (personal project shared to workspace)
        user_workspaces = await db.execute(
            select(WorkspaceMember.workspace_id).where(
                and_(
                    WorkspaceMember.grantee_type == 'user',
                    WorkspaceMember.grantee_id == user_id
                )
            )
        )
        user_workspaces = user_workspaces.scalars().all()
        for ws_id in user_workspaces:
            ws_perm = await db.execute(
                select(ProjectPermission).where(
                    and_(
                        ProjectPermission.project_id == project_id,
                        ProjectPermission.grantee_type == 'workspace',
                        ProjectPermission.grantee_id == ws_id
                    )
                )
            )
            ws_perm = ws_perm.scalar_one_or_none()
            if ws_perm and PermissionService.role_sufficient(ws_perm.role, required_role):
                return True

        return False

    @staticmethod
    async def is_workspace_admin(
        db: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """Check if user is workspace admin"""
        member = await db.execute(
            select(WorkspaceMember).where(
                and_(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.grantee_type == 'user',
                    WorkspaceMember.grantee_id == user_id,
                    WorkspaceMember.role == 'admin'
                )
            )
        )
        return member.scalar_one_or_none() is not None
```

**Step 2: Write failing test for permission checks**

```python
# tests/services/test_permission_service.py
import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.project import Project, ProjectPermission
from core.models.workspace import Workspace, WorkspaceMember
from services.permission_service import PermissionService


@pytest.mark.asyncio
async def test_owner_has_full_access(db_session: AsyncSession):
    """Owner always has full access regardless of role"""
    owner_id = uuid.uuid4()
    project = Project(owner_id=owner_id, name="Test Project")
    db_session.add(project)
    await db_session.commit()

    assert await PermissionService.check_project_access(db_session, owner_id, project.id, 'view')
    assert await PermissionService.check_project_access(db_session, owner_id, project.id, 'edit')
    assert await PermissionService.check_project_access(db_session, owner_id, project.id, 'full')


@pytest.mark.asyncio
async def test_view_role_cannot_edit(db_session: AsyncSession):
    """User with view role cannot edit"""
    owner_id = uuid.uuid4()
    other_user = uuid.uuid4()
    project = Project(owner_id=owner_id, name="Test Project")
    db_session.add(project)
    await db_session.commit()

    permission = ProjectPermission(
        project_id=project.id,
        grantee_type='user',
        grantee_id=other_user,
        role='view',
        granted_by=owner_id
    )
    db_session.add(permission)
    await db_session.commit()

    assert await PermissionService.check_project_access(db_session, other_user, project.id, 'view')
    assert not await PermissionService.check_project_access(db_session, other_user, project.id, 'edit')
```

**Step 3: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/services/test_permission_service.py -v`
Expected: FAIL (tests not written yet)

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/services/test_permission_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/services/permission_service.py
git commit -m "feat(20-01): add permission service with role hierarchy"
```

---

### Task 5: Create Workspaces API Routes

**Files:**
- Create: `backend/api/routes/workspaces.py`
- Modify: `backend/api/main.py`

**Step 1: Write workspace routes**

```python
# backend/api/routes/workspaces.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from core.db import get_db
from core.security.deps import get_current_user
from core.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceMemberCreate,
    WorkspaceResponse,
    WorkspaceListResponse,
    WorkspaceMemberResponse
)
from core.models.workspace import Workspace, WorkspaceMember
from core.models.user import User
from services.permission_service import PermissionService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=List[WorkspaceListResponse])
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List workspaces accessible to user (created by or member)"""
    # Workspaces created by user
    owned_workspaces = await db.execute(
        select(Workspace).where(Workspace.created_by == current_user.id)
    )
    owned_workspaces = owned_workspaces.scalars().all()

    # Workspaces user is member of
    member_workspaces = await db.execute(
        select(Workspace)
        .join(WorkspaceMember)
        .where(
            and_(
                WorkspaceMember.grantee_type == 'user',
                WorkspaceMember.grantee_id == current_user.id
            )
        )
    )
    member_workspaces = member_workspaces.scalars().all()

    # Combine and deduplicate
    all_workspaces = list(set(owned_workspaces + member_workspaces))

    # Enrich with member_count and project_count
    result = []
    for ws in all_workspaces:
        member_count = await db.execute(
            select(func.count()).select_from(WorkspaceMember).where(WorkspaceMember.workspace_id == ws.id)
        )
        project_count = await db.execute(
            select(func.count()).select_from(Workspace).where(Workspace.workspace_id == ws.id)
        )

        result.append(WorkspaceListResponse(
            id=ws.id,
            name=ws.name,
            description=ws.description,
            created_by=ws.created_by,
            status=ws.status,
            created_at=ws.created_at,
            updated_at=ws.updated_at,
            member_count=member_count.scalar(),
            project_count=project_count.scalar()
        ))

    return result


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    workspace: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new workspace"""
    new_workspace = Workspace(
        name=workspace.name,
        description=workspace.description,
        created_by=current_user.id
    )
    db.add(new_workspace)
    await db.commit()
    await db.refresh(new_workspace)
    return new_workspace


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get workspace details (requires membership)"""
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Check if user is member
    is_member = await db.execute(
        select(WorkspaceMember).where(
            and_(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.grantee_type == 'user',
                WorkspaceMember.grantee_id == current_user.id
            )
        )
    )
    is_member = is_member.scalar_one_or_none()

    if workspace.created_by != current_user.id and not is_member:
        raise HTTPException(status_code=403, detail="Not a workspace member")

    return workspace


@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    workspace_update: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update workspace name (admin only)"""
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if not await PermissionService.is_workspace_admin(db, workspace_id, current_user.id):
        raise HTTPException(status_code=403, detail="Must be workspace admin")

    workspace.name = workspace_update.name
    await db.commit()
    await db.refresh(workspace)
    return workspace


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Archive workspace (admin only)"""
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if not await PermissionService.is_workspace_admin(db, workspace_id, current_user.id):
        raise HTTPException(status_code=403, detail="Must be workspace admin")

    workspace.status = 'archived'
    await db.commit()


@router.post("/{workspace_id}/members", response_model=WorkspaceMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_workspace_member(
    workspace_id: str,
    member: WorkspaceMemberCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add member to workspace (admin only)"""
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if not await PermissionService.is_workspace_admin(db, workspace_id, current_user.id):
        raise HTTPException(status_code=403, detail="Must be workspace admin")

    # Check if member already exists
    existing = await db.execute(
        select(WorkspaceMember).where(
            and_(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.grantee_type == member.grantee_type,
                WorkspaceMember.grantee_id == member.grantee_id
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Member already exists")

    new_member = WorkspaceMember(
        workspace_id=workspace_id,
        grantee_type=member.grantee_type,
        grantee_id=member.grantee_id,
        role=member.role,
        added_by=current_user.id
    )
    db.add(new_member)
    await db.commit()
    await db.refresh(new_member)
    return new_member


@router.delete("/{workspace_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_workspace_member(
    workspace_id: str,
    member_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove member from workspace (admin only)"""
    if not await PermissionService.is_workspace_admin(db, workspace_id, current_user.id):
        raise HTTPException(status_code=403, detail="Must be workspace admin")

    member = await db.get(WorkspaceMember, member_id)
    if not member or member.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Member not found")

    await db.delete(member)
    await db.commit()
```

**Step 2: Register router in main.py**

```python
# backend/api/main.py (add import and register)
from api.routes import workspaces

app.include_router(workspaces.router, prefix="/api")
```

**Step 3: Write failing test for workspace API**

```python
# tests/api/test_workspaces.py
import pytest
from fastapi.testclient import TestClient
import uuid

from core.models.workspace import Workspace
from core.models.user import User


@pytest.mark.asyncio
async def test_create_workspace(client: TestClient, db_session):
    """Create workspace as authenticated user"""
    user = User(email="test@example.com")
    db_session.add(user)
    await db_session.commit()

    # Login and get token (implement login helper)
    token = await login_and_get_token(client, user)

    response = client.post(
        "/api/workspaces",
        json={"name": "Test Workspace", "description": "A test"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Workspace"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_workspaces_includes_owned_and_memberships(client: TestClient, db_session):
    """User sees owned workspaces and workspace memberships"""
    user1 = User(email="user1@example.com")
    user2 = User(email="user2@example.com")
    db_session.add_all([user1, user2])
    await db_session.commit()

    token1 = await login_and_get_token(client, user1)

    # Create workspace as user1
    ws_response = client.post(
        "/api/workspaces",
        json={"name": "User1 Workspace"},
        headers={"Authorization": f"Bearer {token1}"}
    )
    workspace_id = ws_response.json()["id"]

    # Add user2 as member
    client.post(
        f"/api/workspaces/{workspace_id}/members",
        json={"grantee_type": "user", "grantee_id": str(user2.id), "role": "member"},
        headers={"Authorization": f"Bearer {token1}"}
    )

    # List workspaces as user2
    token2 = await login_and_get_token(client, user2)
    response = client.get(
        "/api/workspaces",
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert response.status_code == 200
    workspaces = response.json()
    assert len(workspaces) == 1
    assert workspaces[0]["id"] == workspace_id
```

**Step 4: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/api/test_workspaces.py -v`
Expected: FAIL (tests not complete)

**Step 5: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/api/test_workspaces.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/api/routes/workspaces.py backend/api/main.py
git commit -m "feat(20-01): add workspaces CRUD API routes"
```

---

### Task 6: Create Projects API Routes

**Files:**
- Create: `backend/api/routes/projects.py`

**Step 1: Write project routes with permission checks**

```python
# backend/api/routes/projects.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from core.db import get_db
from core.security.deps import get_current_user
from core.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectPublicToggle,
    ProjectPermissionCreate,
    ProjectResponse,
    ProjectListResponse,
    ProjectPermissionResponse
)
from core.models.project import Project, ProjectPermission
from core.models.user import User
from services.permission_service import PermissionService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=List[ProjectListResponse])
async def list_projects(
    workspace_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List projects accessible to user (personal + workspace + shared)"""
    if workspace_id:
        # Filter by workspace
        if not await PermissionService.is_workspace_admin(db, workspace_id, current_user.id):
            # Non-admin: only public projects
            projects = await db.execute(
                select(Project).where(
                    and_(
                        Project.workspace_id == workspace_id,
                        or_(Project.is_public == True, Project.owner_id == current_user.id)
                    )
                )
            )
        else:
            # Admin: all workspace projects
            projects = await db.execute(
                select(Project).where(Project.workspace_id == workspace_id)
            )
    else:
        # Personal projects (workspace_id IS NULL)
        projects = await db.execute(
            select(Project).where(Project.workspace_id == None, Project.owner_id == current_user.id)
        )

    # TODO: Add shared projects via project_permissions
    return projects.scalars().all()


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new project"""
    if project.workspace_id:
        # Check if user is workspace admin
        if not await PermissionService.is_workspace_admin(db, project.workspace_id, current_user.id):
            raise HTTPException(status_code=403, detail="Must be workspace admin to create workspace project")

    new_project = Project(
        owner_id=current_user.id,
        workspace_id=project.workspace_id,
        name=project.name,
        description=project.description
    )
    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)
    return new_project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get project details (requires permission)"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not await PermissionService.check_project_access(db, current_user.id, project.id, 'view'):
        raise HTTPException(status_code=403, detail="No access to this project")

    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_update: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update project (requires edit permission)"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not await PermissionService.check_project_access(db, current_user.id, project.id, 'edit'):
        raise HTTPException(status_code=403, detail="No edit access to this project")

    if project_update.name is not None:
        project.name = project_update.name
    if project_update.description is not None:
        project.description = project_update.description

    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Archive project (requires full permission)"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not await PermissionService.check_project_access(db, current_user.id, project.id, 'full'):
        raise HTTPException(status_code=403, detail="No full access to this project")

    project.status = 'archived'
    await db.commit()


@router.post("/{project_id}/public", response_model=ProjectResponse)
async def toggle_public(
    project_id: str,
    toggle: ProjectPublicToggle,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Toggle public visibility (owner or workspace admin only)"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if owner
    if project.owner_id != current_user.id:
        # Check if workspace admin
        if not project.workspace_id:
            raise HTTPException(status_code=400, detail="Personal projects cannot be public")
        if not await PermissionService.is_workspace_admin(db, project.workspace_id, current_user.id):
            raise HTTPException(status_code=403, detail="Must be owner or workspace admin")

    project.is_public = toggle.is_public
    await db.commit()
    await db.refresh(project)
    return project


@router.post("/{project_id}/permissions", response_model=ProjectPermissionResponse, status_code=status.HTTP_201_CREATED)
async def grant_permission(
    project_id: str,
    permission: ProjectPermissionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Grant permission (owner or full permission required)"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if user has full permission
    if not await PermissionService.check_project_access(db, current_user.id, project.id, 'full'):
        raise HTTPException(status_code=403, detail="Must have full permission to grant access")

    # Cannot grant 'full' if user doesn't have 'full'
    if permission.role == 'full':
        # Owner check already done, this is for permission holders
        if project.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Only owner can grant full permission")

    new_permission = ProjectPermission(
        project_id=project.id,
        grantee_type=permission.grantee_type,
        grantee_id=permission.grantee_id,
        role=permission.role,
        granted_by=current_user.id
    )
    db.add(new_permission)
    await db.commit()
    await db.refresh(new_permission)
    return new_permission


@router.delete("/{project_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_permission(
    project_id: str,
    permission_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke permission (owner or full permission required)"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not await PermissionService.check_project_access(db, current_user.id, project.id, 'full'):
        raise HTTPException(status_code=403, detail="Must have full permission to revoke access")

    permission = await db.get(ProjectPermission, permission_id)
    if not permission or permission.project_id != project.id:
        raise HTTPException(status_code=404, detail="Permission not found")

    await db.delete(permission)
    await db.commit()


@router.get("/{project_id}/permissions", response_model=List[ProjectPermissionResponse])
async def list_permissions(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List project permissions (owner, admin, or full permission required)"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Owner can always see permissions
    if project.owner_id != current_user.id:
        # Non-owner must have full permission or be workspace admin
        if not await PermissionService.check_project_access(db, current_user.id, project.id, 'full'):
            if project.workspace_id:
                if not await PermissionService.is_workspace_admin(db, project.workspace_id, current_user.id):
                    raise HTTPException(status_code=403, detail="No access to permissions")
            else:
                raise HTTPException(status_code=403, detail="No access to permissions")

    permissions = await db.execute(
        select(ProjectPermission).where(ProjectPermission.project_id == project.id)
    )
    return permissions.scalars().all()
```

**Step 2: Register router in main.py**

```python
# backend/api/main.py (add import and register)
from api.routes import projects

app.include_router(projects.router, prefix="/api")
```

**Step 3: Write failing test for project API**

```python
# tests/api/test_projects.py
import pytest
from fastapi.testclient import TestClient

from core.models.project import Project
from core.models.user import User


@pytest.mark.asyncio
async def test_create_personal_project(client: TestClient, db_session):
    """Create personal project without workspace"""
    user = User(email="test@example.com")
    db_session.add(user)
    await db_session.commit()

    token = await login_and_get_token(client, user)

    response = client.post(
        "/api/projects",
        json={"name": "My Project", "description": "Personal notes"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Project"
    assert data["workspace_id"] is None
    assert data["owner_id"] == str(user.id)


@pytest.mark.asyncio
async def test_non_admin_cannot_create_workspace_project(client: TestClient, db_session):
    """Non-workspace admin cannot create workspace project"""
    user = User(email="test@example.com")
    db_session.add(user)
    await db_session.commit()

    token = await login_and_get_token(client, user)

    response = client.post(
        "/api/projects",
        json={"name": "Test Project", "workspace_id": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert "Must be workspace admin" in response.json()["detail"]


@pytest.mark.asyncio
async def test_grant_permission_to_user(client: TestClient, db_session):
    """Owner can grant permission to another user"""
    owner = User(email="owner@example.com")
    other_user = User(email="other@example.com")
    db_session.add_all([owner, other_user])
    await db_session.commit()

    owner_token = await login_and_get_token(client, owner)

    # Create project
    project_response = client.post(
        "/api/projects",
        json={"name": "Shared Project"},
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    project_id = project_response.json()["id"]

    # Grant view permission to other_user
    response = client.post(
        f"/api/projects/{project_id}/permissions",
        json={
            "grantee_type": "user",
            "grantee_id": str(other_user.id),
            "role": "view"
        },
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert response.status_code == 201
    permission = response.json()
    assert permission["grantee_type"] == "user"
    assert permission["role"] == "view"


@pytest.mark.asyncio
async def test_view_permission_grants_access(client: TestClient, db_session):
    """User with view permission can access project"""
    owner = User(email="owner@example.com")
    other_user = User(email="other@example.com")
    db_session.add_all([owner, other_user])
    await db_session.commit()

    owner_token = await login_and_get_token(client, owner)

    # Create project and grant permission
    project_response = client.post(
        "/api/projects",
        json={"name": "Shared Project"},
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    project_id = project_response.json()["id"]

    client.post(
        f"/api/projects/{project_id}/permissions",
        json={"grantee_type": "user", "grantee_id": str(other_user.id), "role": "view"},
        headers={"Authorization": f"Bearer {owner_token}"}
    )

    # Other user can access project
    other_token = await login_and_get_token(client, other_user)
    response = client.get(
        f"/api/projects/{project_id}",
        headers={"Authorization": f"Bearer {other_token}"}
    )
    assert response.status_code == 200
    assert response.json()["id"] == project_id


@pytest.mark.asyncio
async def test_view_role_cannot_edit(client: TestClient, db_session):
    """User with view role cannot edit project"""
    owner = User(email="owner@example.com")
    other_user = User(email="other@example.com")
    db_session.add_all([owner, other_user])
    await db_session.commit()

    owner_token = await login_and_get_token(client, owner)

    # Create project and grant view permission
    project_response = client.post(
        "/api/projects",
        json={"name": "Shared Project"},
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    project_id = project_response.json()["id"]

    client.post(
        f"/api/projects/{project_id}/permissions",
        json={"grantee_type": "user", "grantee_id": str(other_user.id), "role": "view"},
        headers={"Authorization": f"Bearer {owner_token}"}
    )

    # Other user cannot edit
    other_token = await login_and_get_token(client, other_user)
    response = client.put(
        f"/api/projects/{project_id}",
        json={"name": "Renamed"},
        headers={"Authorization": f"Bearer {other_token}"}
    )
    assert response.status_code == 403
```

**Step 4: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/api/test_projects.py -v`
Expected: FAIL (tests not complete)

**Step 5: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/api/test_projects.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/api/routes/projects.py backend/api/main.py
git commit -m "feat(20-01): add projects CRUD API routes with permissions"
```

---

## Phase 2: NotebookLM Core (Week 3-4)

[Continue with similar detailed tasks for:]
- Task 7: Create migration for project_sources and project_sections
- Task 8: Create source and section models
- Task 9: Create Celery task for embedding generation
- Task 10: Create sources API routes
- Task 11: Create sections API routes

---

## Phase 3: Chat & Insights (Week 5-6)

[Continue with similar detailed tasks for:]
- Task 12: Create migration for project_chats and project_insights
- Task 13: Create chat and insight models
- Task 14: Create Celery task for AI insights generation
- Task 15: Create chats API routes (RAG implementation)
- Task 16: Create insights API routes

---

## Phase 4: Advanced Features (Week 7-8)

[Continue with similar detailed tasks for:]
- Task 17: Create migration for project_backups
- Task 18: Create backup model and schema
- Task 19: Create Celery task for backup generation
- Task 20: Create Celery task for restore operation
- Task 21: Create backup/restore API routes

---

## Phase 5: Polish & Hardening (Week 9-10)

[Continue with similar detailed tasks for:]
- Task 22: Write comprehensive E2E tests (Playwright)
- Task 23: Implement left navigation integration
- Task 24: Add error handling and validation
- Task 25: Performance testing and optimization
- Task 26: Documentation and deployment guides

---

## Testing & Verification

### Run Full Test Suite

```bash
# Backend tests
PYTHONPATH=. .venv/bin/pytest tests/api/test_workspaces.py tests/api/test_projects.py -v

# Permission service tests
PYTHONPATH=. .venv/bin/pytest tests/services/test_permission_service.py -v

# Model tests
PYTHONPATH=. .venv/bin/pytest tests/models/test_workspace.py tests/models/test_project.py -v
```

### Manual Verification Checklist

- [ ] User can create personal project
- [ ] User can create workspace
- [ ] Workspace admin can create workspace project
- [ ] User can share personal project to workspace
- [ ] Workspace members can see public workspace projects
- [ ] Permission model enforces view/edit/full hierarchy
- [ ] User can create notes, files, markdown in project
- [ ] User can create hierarchical sections/folders
- [ ] Semantic search returns relevant sources
- [ ] Chat with sources includes citations
- [ ] AI insights are generated for sources
- [ ] Workspace admin can create backup
- [ ] Restore creates new project with auto-rename

---

## Notes for Implementation

### Important Gotchas

1. **workspace_id NULL means personal project** - Never assign `workspace_id = ''`, use `None`
2. **is_public only for workspace projects** - Personal projects cannot be public
3. **Sharing doesn't change ownership** - Personal project shared to workspace stays personal
4. **Embedding generation is async** - Don't block API, use Celery tasks
5. **pgvector extension required** - Ensure PostgreSQL has pgvector installed
6. **Role hierarchy enforced** - view < edit < full, use `PermissionService.role_sufficient()`
7. **Cascade deletes** - Workspace delete cascades to members, project delete cascades to permissions

### Dependencies

- Storage Service (Topic #19) must be implemented for file uploads
- LiteLLM Proxy must be running for LLM calls (blitz/master alias)
- Redis must be running for Celery broker
- PostgreSQL must have pgvector extension enabled

### Integration Points

- **Frontend:** Next.js pages for `/projects`, `/workspaces`, `/project/{id}`
- **Navigation:** `/api/user/context` endpoint for left panel
- **Storage:** Use Storage Service API for file uploads/backup ZIP storage
- **LLM:** Use `get_llm("blitz/master")` for chat and insights
- **Embedding:** Use `EmbeddingService.get_model()` for semantic search
