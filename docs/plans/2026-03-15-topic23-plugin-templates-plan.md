# Topic #23: Plugin Templates Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Build a complete Template System for AgentOS that allows admins to import/export ZIP-based templates, deploy them to companies, and enable users to discover and subscribe to template agents through a self-service gallery.

**Architecture:** Template-Aware Entities approach with 4 new database tables (template, template_entity, template_instance, template_user_assignment) tracking full lineage from global template registry to per-company deployments. ZIP-based template format with JSON manifests for portability.

**Tech Stack:** FastAPI, PostgreSQL, SQLAlchemy, Alembic, React/Next.js, TypeScript, Tailwind CSS

**Design Document:** [2026-03-15-topic23-plugin-templates-design.md](./2026-03-15-topic23-plugin-templates-design.md)

---

## Phase 1: Foundation - Database Schema (Tasks 1-6)

### Task 1: Create Template Table Migration

**Files:**
- Create: `backend/alembic/versions/032_template_tables.py`

**Step 1: Generate migration file**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
.venv/bin/alembic revision -m "032_add_template_tables"
```

**Step 2: Write migration for template table**

```python
"""032_add_template_tables

Revision ID: 032_template_tables
Revises: 031_merge_heads
Create Date: 2026-03-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '032_template_tables'
down_revision = '031_merge_heads'
branch_labels = None
depends_on = None


def upgrade():
    # Create template table
    op.create_table(
        'template',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('slug', sa.String(100), unique=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('category', sa.String(50)),
        sa.Column('target_company_size', sa.String(20)),
        sa.Column('author', sa.String(100)),
        sa.Column('license', sa.String(50)),
        sa.Column('manifest_json', postgresql.JSONB, nullable=False),
        sa.Column('is_system', sa.Boolean, default=False),
        sa.Column('status', sa.String(20), default='active'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now())
    )
    
    # Create indexes
    op.create_index('idx_template_category', 'template', ['category'])
    op.create_index('idx_template_status', 'template', ['status'])


def downgrade():
    op.drop_index('idx_template_status', table_name='template')
    op.drop_index('idx_template_category', table_name='template')
    op.drop_table('template')
```

**Step 3: Run migration to verify it works**

```bash
cd /home/tungmv/Projects/hox-agentos
just migrate
```

Expected: Migration applies successfully

**Step 4: Commit**

```bash
git add backend/alembic/versions/032_template_tables.py
git commit -m "feat(23-01): add template table migration"
```

---

### Task 2: Create TemplateEntity Table Migration

**Files:**
- Modify: `backend/alembic/versions/032_template_tables.py` (add to existing migration)

**Step 1: Add template_entity table to migration**

Edit the migration file to add:

```python
def upgrade():
    # ... existing template table ...
    
    # Create template_entity table
    op.create_table(
        'template_entity',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('template.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entity_type', sa.String(20), nullable=False),
        sa.Column('entity_key', sa.String(100), nullable=False),
        sa.Column('entity_data', postgresql.JSONB, nullable=False),
        sa.Column('display_order', sa.Integer, default=0),
        sa.Column('tags', postgresql.ARRAY(sa.String)),
        sa.Column('dependencies', postgresql.ARRAY(sa.String)),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.UniqueConstraint('template_id', 'entity_type', 'entity_key')
    )
    
    # Create indexes
    op.create_index('idx_template_entity_template', 'template_entity', ['template_id'])
    op.create_index('idx_template_entity_type', 'template_entity', ['entity_type'])
    op.create_index('idx_template_entity_tags', 'template_entity', ['tags'], postgresql_using='gin')


def downgrade():
    # ... existing downgrade ...
    op.drop_index('idx_template_entity_tags', table_name='template_entity')
    op.drop_index('idx_template_entity_type', table_name='template_entity')
    op.drop_index('idx_template_entity_template', table_name='template_entity')
    op.drop_table('template_entity')
```

**Step 2: Verify migration still works**

```bash
just migrate
```

**Step 3: Commit**

```bash
git add backend/alembic/versions/032_template_tables.py
git commit -m "feat(23-02): add template_entity table migration"
```

---

### Task 3: Create TemplateInstance and TemplateUserAssignment Tables

**Files:**
- Modify: `backend/alembic/versions/032_template_tables.py`

**Step 1: Add remaining tables to migration**

```python
def upgrade():
    # ... existing tables ...
    
    # Create template_instance table
    op.create_table(
        'template_instance',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('template.id'), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('deployed_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(20), default='active'),
        sa.Column('deployed_at', sa.DateTime, default=sa.func.now()),
        sa.Column('last_sync_at', sa.DateTime),
        sa.Column('deployment_config', postgresql.JSONB),
        sa.Column('forked_entities', postgresql.ARRAY(postgresql.UUID(as_uuid=True))),
        sa.Column('metadata_json', postgresql.JSONB),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now())
    )
    
    op.create_index('idx_template_instance_company', 'template_instance', ['company_id'])
    op.create_index('idx_template_instance_template', 'template_instance', ['template_id'])
    op.create_index('idx_template_instance_status', 'template_instance', ['status'])
    
    # Create template_user_assignment table
    op.create_table(
        'template_user_assignment',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('instance_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('template_instance.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_type', sa.String(20), nullable=False),
        sa.Column('entity_key', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), default='active'),
        sa.Column('assigned_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_at', sa.DateTime, default=sa.func.now()),
        sa.Column('config_overrides', postgresql.JSONB),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now())
    )
    
    op.create_index('idx_template_assignment_instance', 'template_user_assignment', ['instance_id'])
    op.create_index('idx_template_assignment_user', 'template_user_assignment', ['user_id'])
    op.create_index('idx_template_assignment_status', 'template_user_assignment', ['status'])


def downgrade():
    # ... existing ...
    op.drop_index('idx_template_assignment_status', table_name='template_user_assignment')
    op.drop_index('idx_template_assignment_user', table_name='template_user_assignment')
    op.drop_index('idx_template_assignment_instance', table_name='template_user_assignment')
    op.drop_table('template_user_assignment')
    
    op.drop_index('idx_template_instance_status', table_name='template_instance')
    op.drop_index('idx_template_instance_template', table_name='template_instance')
    op.drop_index('idx_template_instance_company', table_name='template_instance')
    op.drop_table('template_instance')
    # ... rest of downgrade ...
```

**Step 2: Add template_origin column to existing tables**

```python
def upgrade():
    # ... existing ...
    
    # Add template_origin tracking to existing entities
    op.add_column('agent', sa.Column('template_origin', postgresql.JSONB))
    op.add_column('skill', sa.Column('template_origin', postgresql.JSONB))
    op.add_column('tool_registry', sa.Column('template_origin', postgresql.JSONB))


def downgrade():
    # Remove template_origin columns first (in reverse order)
    op.drop_column('tool_registry', 'template_origin')
    op.drop_column('skill', 'template_origin')
    op.drop_column('agent', 'template_origin')
    # ... rest ...
```

**Step 3: Run migration**

```bash
just migrate
```

**Step 4: Commit**

```bash
git add backend/alembic/versions/032_template_tables.py
git commit -m "feat(23-03): add template_instance, template_user_assignment tables and origin tracking"
```

---

### Task 4: Create SQLAlchemy Models

**Files:**
- Create: `backend/core/models/template.py`

**Step 1: Write the models file**

```python
"""Template system SQLAlchemy models."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import String, Text, Boolean, DateTime, Integer, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class Template(Base):
    """Global template registry."""
    __tablename__ = "template"
    
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50))
    target_company_size: Mapped[Optional[str]] = mapped_column(String(20))
    author: Mapped[Optional[str]] = mapped_column(String(100))
    license: Mapped[Optional[str]] = mapped_column(String(50))
    manifest_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    entities: Mapped[List["TemplateEntity"]] = relationship("TemplateEntity", back_populates="template", cascade="all, delete-orphan")
    instances: Mapped[List["TemplateInstance"]] = relationship("TemplateInstance", back_populates="template")
    
    __table_args__ = (
        Index("idx_template_category", "category"),
        Index("idx_template_status", "status"),
    )


class TemplateEntity(Base):
    """Individual agents, skills, and tools within a template."""
    __tablename__ = "template_entity"
    
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    template_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("template.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_key: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    dependencies: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    template: Mapped["Template"] = relationship("Template", back_populates="entities")
    
    __table_args__ = (
        UniqueConstraint("template_id", "entity_type", "entity_key"),
        Index("idx_template_entity_template", "template_id"),
        Index("idx_template_entity_type", "entity_type"),
        Index("idx_template_entity_tags", "tags", postgresql_using="gin"),
    )


class TemplateInstance(Base):
    """Per-company deployment of a template."""
    __tablename__ = "template_instance"
    
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    template_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("template.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    deployed_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    deployed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    deployment_config: Mapped[Optional[dict]] = mapped_column(JSONB)
    forked_entities: Mapped[Optional[List[UUID]]] = mapped_column(ARRAY(PGUUID(as_uuid=True)))
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    template: Mapped["Template"] = relationship("Template", back_populates="instances")
    assignments: Mapped[List["TemplateUserAssignment"]] = relationship("TemplateUserAssignment", back_populates="instance", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_template_instance_company", "company_id"),
        Index("idx_template_instance_template", "template_id"),
        Index("idx_template_instance_status", "status"),
    )


class TemplateUserAssignment(Base):
    """Which users have access to which template entities."""
    __tablename__ = "template_user_assignment"
    
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    instance_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("template_instance.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    assigned_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    config_overrides: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    instance: Mapped["TemplateInstance"] = relationship("TemplateInstance", back_populates="assignments")
    
    __table_args__ = (
        Index("idx_template_assignment_instance", "instance_id"),
        Index("idx_template_assignment_user", "user_id"),
        Index("idx_template_assignment_status", "status"),
    )
```

**Step 2: Add models to __init__.py**

Modify: `backend/core/models/__init__.py`

```python
# Add imports
from core.models.template import Template, TemplateEntity, TemplateInstance, TemplateUserAssignment

__all__ = [
    # ... existing exports ...
    "Template",
    "TemplateEntity", 
    "TemplateInstance",
    "TemplateUserAssignment",
]
```

**Step 3: Test the models import correctly**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/python -c "from core.models import Template, TemplateEntity, TemplateInstance, TemplateUserAssignment; print('Models imported successfully')"
```

Expected: `Models imported successfully`

**Step 4: Commit**

```bash
git add backend/core/models/template.py backend/core/models/__init__.py
git commit -m "feat(23-04): add Template SQLAlchemy models"
```

---

### Task 5: Create Pydantic Schemas

**Files:**
- Create: `backend/core/schemas/template.py`

**Step 1: Write the schemas file**

```python
"""Template system Pydantic schemas."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


# ============== Template Schemas ==============

class TemplateManifest(BaseModel):
    """Template manifest schema."""
    spec_version: str
    template: Dict[str, Any]
    entities: Dict[str, Any]
    deployment: Optional[Dict[str, Any]] = None


class TemplateBase(BaseModel):
    """Base template schema."""
    slug: str = Field(..., max_length=100)
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    version: str = Field(..., max_length=20)
    category: Optional[str] = Field(None, max_length=50)
    target_company_size: Optional[str] = Field(None, max_length=20)
    author: Optional[str] = Field(None, max_length=100)
    license: Optional[str] = Field(None, max_length=50)
    manifest: Dict[str, Any] = Field(..., alias="manifest_json")
    is_system: bool = False
    status: str = "active"


class TemplateCreate(TemplateBase):
    """Schema for creating a template."""
    pass


class TemplateUpdate(BaseModel):
    """Schema for updating a template."""
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = Field(None, max_length=20)


class TemplateResponse(TemplateBase):
    """Schema for template response."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    entity_counts: Optional[Dict[str, int]] = None
    
    class Config:
        from_attributes = True


class TemplateListResponse(BaseModel):
    """Schema for template list response."""
    id: UUID
    slug: str
    name: str
    version: str
    category: Optional[str]
    status: str
    deployment_count: int = 0
    entity_counts: Dict[str, int]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TemplateDetailResponse(TemplateResponse):
    """Detailed template response with entities."""
    entities: Dict[str, List[Dict[str, Any]]]


# ============== TemplateEntity Schemas ==============

class TemplateEntityBase(BaseModel):
    """Base template entity schema."""
    entity_type: str = Field(..., pattern="^(agent|skill|tool)$")
    entity_key: str = Field(..., max_length=100)
    entity_data: Dict[str, Any]
    display_order: int = 0
    tags: Optional[List[str]] = None
    dependencies: Optional[List[str]] = None


class TemplateEntityResponse(TemplateEntityBase):
    """Schema for template entity response."""
    id: UUID
    template_id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============== TemplateInstance Schemas ==============

class TemplateInstanceBase(BaseModel):
    """Base template instance schema."""
    template_id: UUID
    company_id: UUID
    status: str = "active"


class TemplateInstanceCreate(TemplateInstanceBase):
    """Schema for creating template instance."""
    deployment_config: Optional[Dict[str, Any]] = None
    assignments: Optional[Dict[str, List[UUID]]] = None  # entity_key -> user_ids
    enable_self_service: bool = True


class TemplateInstanceUpdate(BaseModel):
    """Schema for updating template instance."""
    status: Optional[str] = Field(None, max_length=20)


class TemplateInstanceResponse(TemplateInstanceBase):
    """Schema for template instance response."""
    id: UUID
    deployed_by: UUID
    deployed_at: datetime
    last_sync_at: Optional[datetime]
    entity_counts: Dict[str, int]
    user_count: int = 0
    
    class Config:
        from_attributes = True


class TemplateInstanceListResponse(BaseModel):
    """Schema for company template instances list."""
    instance_id: UUID
    template: Dict[str, Any]
    status: str
    deployed_at: datetime
    user_count: int
    entity_counts: Dict[str, int]


# ============== TemplateUserAssignment Schemas ==============

class TemplateUserAssignmentBase(BaseModel):
    """Base assignment schema."""
    user_id: UUID
    entity_type: str
    entity_key: str
    status: str = "active"


class TemplateUserAssignmentCreate(BaseModel):
    """Schema for creating assignment."""
    user_id: UUID
    entity_key: str
    action: str = Field(..., pattern="^(assign|revoke)$")
    config_overrides: Optional[Dict[str, Any]] = None


class TemplateUserAssignmentResponse(TemplateUserAssignmentBase):
    """Schema for assignment response."""
    id: UUID
    instance_id: UUID
    assigned_by: UUID
    assigned_at: datetime
    config_overrides: Optional[Dict[str, Any]]
    
    class Config:
        from_attributes = True


# ============== Import/Export Schemas ==============

class TemplateImportResponse(BaseModel):
    """Schema for template import response."""
    template_id: UUID
    slug: str
    name: str
    version: str
    entities_imported: Dict[str, int]
    warnings: List[str]
    status: str


class TemplateDeployResponse(BaseModel):
    """Schema for template deploy response."""
    instance_id: UUID
    template_id: UUID
    company_id: UUID
    status: str
    entities_deployed: Dict[str, int]
    assignments_created: int
    deployed_at: datetime


class TemplateGalleryItem(BaseModel):
    """Schema for template gallery item."""
    id: UUID
    name: str
    description: Optional[str]
    category: Optional[str]
    tags: List[str]
    icon_url: Optional[str]
    is_deployed: bool
    has_access: List[str]
    available_agents: List[Dict[str, Any]]


class UserTemplateAgent(BaseModel):
    """Schema for user's template agent."""
    agent_id: UUID
    name: str
    description: Optional[str]
    icon: Optional[str]
    template: Dict[str, Any]
    instance_id: UUID
    assigned_at: datetime
    last_used: Optional[datetime]
```

**Step 2: Add to __init__.py**

Modify: `backend/core/schemas/__init__.py`

```python
from core.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateListResponse,
    TemplateDetailResponse,
    TemplateImportResponse,
    TemplateDeployResponse,
    TemplateInstanceCreate,
    TemplateInstanceUpdate,
    TemplateInstanceResponse,
    TemplateInstanceListResponse,
    TemplateUserAssignmentCreate,
    TemplateUserAssignmentResponse,
    TemplateGalleryItem,
    UserTemplateAgent,
)

__all__ = [
    # ... existing ...
    "TemplateCreate",
    "TemplateUpdate",
    "TemplateResponse",
    "TemplateListResponse",
    "TemplateDetailResponse",
    "TemplateImportResponse",
    "TemplateDeployResponse",
    "TemplateInstanceCreate",
    "TemplateInstanceUpdate",
    "TemplateInstanceResponse",
    "TemplateInstanceListResponse",
    "TemplateUserAssignmentCreate",
    "TemplateUserAssignmentResponse",
    "TemplateGalleryItem",
    "UserTemplateAgent",
]
```

**Step 3: Verify imports**

```bash
PYTHONPATH=. .venv/bin/python -c "from core.schemas.template import TemplateResponse; print('Schemas imported successfully')"
```

**Step 4: Commit**

```bash
git add backend/core/schemas/template.py backend/core/schemas/__init__.py
git commit -m "feat(23-05): add Template Pydantic schemas"
```

---

### Task 6: Create ZIP Parser Service

**Files:**
- Create: `backend/services/template_parser.py`
- Create: `backend/tests/services/test_template_parser.py`

**Step 1: Write the parser service**

```python
"""Template ZIP parser service."""

import json
import zipfile
from io import BytesIO
from typing import Dict, List, Any, Tuple
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


class TemplateValidationError(Exception):
    """Raised when template validation fails."""
    pass


class TemplateParser:
    """Parse and validate template ZIP files."""
    
    REQUIRED_FILES = ["template.json"]
    VALID_ENTITY_TYPES = ["agent", "skill", "tool"]
    SUPPORTED_SPEC_VERSIONS = ["1.0"]
    
    def __init__(self, zip_content: bytes):
        self.zip_content = zip_content
        self.warnings: List[str] = []
        
    def parse(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Parse template ZIP and return manifest + entities.
        
        Returns:
            Tuple of (manifest_dict, entities_list)
            
        Raises:
            TemplateValidationError: If template is invalid
        """
        try:
            with zipfile.ZipFile(BytesIO(self.zip_content)) as zf:
                # Check required files
                file_list = zf.namelist()
                self._check_required_files(file_list)
                
                # Parse manifest
                manifest = self._parse_manifest(zf)
                
                # Parse entities
                entities = self._parse_entities(zf, manifest)
                
                # Validate entity counts
                self._validate_entity_counts(manifest, entities)
                
                return manifest, entities
                
        except zipfile.BadZipFile:
            raise TemplateValidationError("Invalid ZIP file format")
        except Exception as e:
            logger.error("template_parse_error", error=str(e))
            raise TemplateValidationError(f"Failed to parse template: {str(e)}")
    
    def _check_required_files(self, file_list: List[str]) -> None:
        """Check that required files exist in ZIP."""
        for required in self.REQUIRED_FILES:
            if required not in file_list:
                raise TemplateValidationError(f"Missing required file: {required}")
    
    def _parse_manifest(self, zf: zipfile.ZipFile) -> Dict[str, Any]:
        """Parse and validate template.json manifest."""
        try:
            manifest_content = zf.read("template.json").decode("utf-8")
            manifest = json.loads(manifest_content)
        except json.JSONDecodeError as e:
            raise TemplateValidationError(f"Invalid JSON in template.json: {str(e)}")
        
        # Validate spec version
        spec_version = manifest.get("spec_version")
        if spec_version not in self.SUPPORTED_SPEC_VERSIONS:
            raise TemplateValidationError(
                f"Unsupported spec version: {spec_version}. "
                f"Supported: {self.SUPPORTED_SPEC_VERSIONS}"
            )
        
        # Validate required sections
        if "template" not in manifest:
            raise TemplateValidationError("Missing 'template' section in manifest")
        
        template_section = manifest["template"]
        required_fields = ["slug", "name", "version"]
        for field in required_fields:
            if field not in template_section:
                raise TemplateValidationError(f"Missing required field in template: {field}")
        
        if "entities" not in manifest:
            raise TemplateValidationError("Missing 'entities' section in manifest")
        
        return manifest
    
    def _parse_entities(self, zf: zipfile.ZipFile, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse all entity files from ZIP."""
        entities = []
        entity_config = manifest.get("entities", {})
        
        for entity_type in self.VALID_ENTITY_TYPES:
            type_config = entity_config.get(entity_type, {})
            files = type_config.get("files", [])
            
            for file_name in files:
                entity_path = f"{entity_type}s/{file_name}"
                
                if entity_path not in zf.namelist():
                    self.warnings.append(f"Entity file not found: {entity_path}")
                    continue
                
                try:
                    entity_content = zf.read(entity_path).decode("utf-8")
                    entity_data = json.loads(entity_content)
                    
                    # Validate entity structure
                    self._validate_entity(entity_data, entity_type)
                    
                    entities.append({
                        "entity_type": entity_type,
                        "entity_key": entity_data.get("entity_key"),
                        "entity_data": entity_data
                    })
                    
                except json.JSONDecodeError as e:
                    self.warnings.append(f"Invalid JSON in {entity_path}: {str(e)}")
                except TemplateValidationError as e:
                    self.warnings.append(f"Validation error in {entity_path}: {str(e)}")
        
        return entities
    
    def _validate_entity(self, entity_data: Dict[str, Any], expected_type: str) -> None:
        """Validate individual entity structure."""
        entity_type = entity_data.get("entity_type")
        if entity_type != expected_type:
            raise TemplateValidationError(
                f"Entity type mismatch: expected {expected_type}, got {entity_type}"
            )
        
        if "entity_key" not in entity_data:
            raise TemplateValidationError("Missing 'entity_key' in entity")
        
        if "name" not in entity_data:
            raise TemplateValidationError(f"Missing 'name' in entity: {entity_data.get('entity_key')}")
    
    def _validate_entity_counts(self, manifest: Dict[str, Any], entities: List[Dict[str, Any]]) -> None:
        """Validate that entity counts match manifest."""
        entity_config = manifest.get("entities", {})
        
        for entity_type in self.VALID_ENTITY_TYPES:
            expected_count = entity_config.get(entity_type, {}).get("count", 0)
            actual_count = len([e for e in entities if e["entity_type"] == entity_type])
            
            if expected_count != actual_count:
                self.warnings.append(
                    f"{entity_type} count mismatch: expected {expected_count}, got {actual_count}"
                )
    
    def get_warnings(self) -> List[str]:
        """Return list of validation warnings."""
        return self.warnings


def parse_template_zip(zip_content: bytes) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[str]]:
    """Convenience function to parse template ZIP.
    
    Returns:
        Tuple of (manifest, entities, warnings)
    """
    parser = TemplateParser(zip_content)
    manifest, entities = parser.parse()
    return manifest, entities, parser.get_warnings()
```

**Step 2: Write tests for the parser**

```python
"""Tests for template parser service."""

import json
import zipfile
from io import BytesIO

import pytest

from services.template_parser import TemplateParser, TemplateValidationError, parse_template_zip


class TestTemplateParser:
    """Test template parser functionality."""
    
    def _create_valid_template_zip(self) -> bytes:
        """Create a valid template ZIP for testing."""
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add manifest
            manifest = {
                "spec_version": "1.0",
                "template": {
                    "slug": "test-template",
                    "name": "Test Template",
                    "version": "1.0.0",
                    "category": "test"
                },
                "entities": {
                    "agents": {
                        "count": 1,
                        "files": ["test-agent.json"]
                    },
                    "skills": {"count": 0, "files": []},
                    "tools": {"count": 0, "files": []}
                }
            }
            zf.writestr("template.json", json.dumps(manifest))
            
            # Add agent
            agent = {
                "entity_type": "agent",
                "entity_key": "test-agent",
                "name": "Test Agent",
                "description": "A test agent"
            }
            zf.writestr("agents/test-agent.json", json.dumps(agent))
        
        return buffer.getvalue()
    
    def _create_invalid_zip(self) -> bytes:
        """Create an invalid (non-ZIP) file."""
        return b"not a zip file"
    
    def test_parse_valid_template(self):
        """Test parsing a valid template ZIP."""
        zip_content = self._create_valid_template_zip()
        manifest, entities, warnings = parse_template_zip(zip_content)
        
        assert manifest["template"]["slug"] == "test-template"
        assert manifest["template"]["name"] == "Test Template"
        assert len(entities) == 1
        assert entities[0]["entity_type"] == "agent"
        assert entities[0]["entity_key"] == "test-agent"
    
    def test_parse_invalid_zip(self):
        """Test parsing invalid ZIP file."""
        with pytest.raises(TemplateValidationError) as exc_info:
            parse_template_zip(self._create_invalid_zip())
        
        assert "Invalid ZIP file" in str(exc_info.value)
    
    def test_missing_manifest(self):
        """Test ZIP without template.json."""
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("other.txt", "content")
        
        with pytest.raises(TemplateValidationError) as exc_info:
            parse_template_zip(buffer.getvalue())
        
        assert "Missing required file: template.json" in str(exc_info.value)
    
    def test_invalid_spec_version(self):
        """Test template with unsupported spec version."""
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            manifest = {"spec_version": "2.0", "template": {"slug": "test", "name": "Test", "version": "1.0"}}
            zf.writestr("template.json", json.dumps(manifest))
        
        with pytest.raises(TemplateValidationError) as exc_info:
            parse_template_zip(buffer.getvalue())
        
        assert "Unsupported spec version" in str(exc_info.value)
    
    def test_missing_required_fields(self):
        """Test manifest missing required fields."""
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            manifest = {"spec_version": "1.0", "template": {}}
            zf.writestr("template.json", json.dumps(manifest))
        
        with pytest.raises(TemplateValidationError) as exc_info:
            parse_template_zip(buffer.getvalue())
        
        assert "Missing required field" in str(exc_info.value)
```

**Step 3: Run the tests**

```bash
PYTHONPATH=. .venv/bin/pytest backend/tests/services/test_template_parser.py -v
```

Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/services/template_parser.py backend/tests/services/test_template_parser.py
git commit -m "feat(23-06): add Template ZIP parser service with tests"
```

---

## Phase 2: Admin API Endpoints (Tasks 7-12)

### Task 7: Create Template Import Service

**Files:**
- Create: `backend/services/template_service.py`
- Create: `backend/tests/services/test_template_service.py`

**Step 1: Write the template service**

```python
"""Template management service."""

from typing import Optional, List, Dict, Any
from uuid import UUID
import structlog

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Template, TemplateEntity
from core.schemas import TemplateCreate, TemplateUpdate
from services.template_parser import parse_template_zip

logger = structlog.get_logger(__name__)


class TemplateService:
    """Service for managing templates."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def import_template(self, zip_content: bytes) -> Dict[str, Any]:
        """Import template from ZIP file.
        
        Returns:
            Dict with template_id, entities_imported, warnings
        """
        # Parse ZIP
        manifest, entities, warnings = parse_template_zip(zip_content)
        template_section = manifest["template"]
        
        # Check for duplicate slug
        existing = await self.get_by_slug(template_section["slug"])
        if existing:
            raise ValueError(f"Template with slug '{template_section['slug']}' already exists")
        
        # Create template record
        template = Template(
            slug=template_section["slug"],
            name=template_section["name"],
            description=template_section.get("description"),
            version=template_section["version"],
            category=template_section.get("category"),
            target_company_size=template_section.get("target_company_size"),
            author=template_section.get("author"),
            license=template_section.get("license"),
            manifest_json=manifest,
            is_system=template_section.get("is_system", False),
            status="active"
        )
        
        self.session.add(template)
        await self.session.flush()  # Get template.id
        
        # Create entity records
        entity_counts = {"agents": 0, "skills": 0, "tools": 0}
        
        for entity_data in entities:
            entity = TemplateEntity(
                template_id=template.id,
                entity_type=entity_data["entity_type"],
                entity_key=entity_data["entity_key"],
                entity_data=entity_data["entity_data"],
                display_order=entity_data["entity_data"].get("display_order", 0),
                tags=entity_data["entity_data"].get("tags"),
                dependencies=entity_data["entity_data"].get("dependencies")
            )
            self.session.add(entity)
            entity_counts[entity_data["entity_type"] + "s"] += 1
        
        await self.session.commit()
        
        logger.info(
            "template_imported",
            template_id=str(template.id),
            slug=template.slug,
            entities_imported=entity_counts
        )
        
        return {
            "template_id": template.id,
            "slug": template.slug,
            "name": template.name,
            "version": template.version,
            "entities_imported": entity_counts,
            "warnings": warnings
        }
    
    async def get_by_slug(self, slug: str) -> Optional[Template]:
        """Get template by slug."""
        result = await self.session.execute(
            select(Template).where(Template.slug == slug)
        )
        return result.scalar_one_or_none()
    
    async def get_by_id(self, template_id: UUID) -> Optional[Template]:
        """Get template by ID."""
        result = await self.session.execute(
            select(Template).where(Template.id == template_id)
        )
        return result.scalar_one_or_none()
    
    async def list_templates(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        """List templates with pagination and filters."""
        query = select(Template)
        
        if category:
            query = query.where(Template.category == category)
        if status:
            query = query.where(Template.status == status)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.session.scalar(count_query)
        
        # Get paginated results
        query = query.order_by(Template.created_at.desc())
        query = query.offset((page - 1) * limit).limit(limit)
        
        result = await self.session.execute(query)
        templates = result.scalars().all()
        
        # Calculate entity counts and deployment counts
        template_list = []
        for template in templates:
            entity_counts = await self._get_entity_counts(template.id)
            deployment_count = await self._get_deployment_count(template.id)
            
            template_list.append({
                "id": template.id,
                "slug": template.slug,
                "name": template.name,
                "version": template.version,
                "category": template.category,
                "status": template.status,
                "deployment_count": deployment_count,
                "entity_counts": entity_counts,
                "created_at": template.created_at,
                "updated_at": template.updated_at
            })
        
        return {
            "templates": template_list,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
    
    async def _get_entity_counts(self, template_id: UUID) -> Dict[str, int]:
        """Get entity counts for a template."""
        result = await self.session.execute(
            select(TemplateEntity.entity_type, func.count())
            .where(TemplateEntity.template_id == template_id)
            .group_by(TemplateEntity.entity_type)
        )
        counts = {"agents": 0, "skills": 0, "tools": 0}
        for entity_type, count in result.all():
            counts[entity_type + "s"] = count
        return counts
    
    async def _get_deployment_count(self, template_id: UUID) -> int:
        """Get number of deployments for a template."""
        from core.models import TemplateInstance
        result = await self.session.execute(
            select(func.count())
            .select_from(TemplateInstance)
            .where(TemplateInstance.template_id == template_id)
        )
        return result.scalar()
    
    async def update_template(
        self,
        template_id: UUID,
        update_data: TemplateUpdate
    ) -> Optional[Template]:
        """Update template."""
        template = await self.get_by_id(template_id)
        if not template:
            return None
        
        if update_data.name is not None:
            template.name = update_data.name
        if update_data.description is not None:
            template.description = update_data.description
        if update_data.status is not None:
            template.status = update_data.status
        
        await self.session.commit()
        return template
    
    async def delete_template(self, template_id: UUID, force: bool = False) -> Dict[str, Any]:
        """Delete template and its entities.
        
        Args:
            template_id: Template to delete
            force: If True, delete even if deployed
            
        Returns:
            Dict with deleted status and counts
        """
        template = await self.get_by_id(template_id)
        if not template:
            raise ValueError("Template not found")
        
        # Check for active deployments
        from core.models import TemplateInstance
        deployment_count = await self._get_deployment_count(template_id)
        
        if deployment_count > 0 and not force:
            raise ValueError(
                f"Template has {deployment_count} active deployments. "
                "Use force=True to delete anyway."
            )
        
        # Get entity count before deletion
        entity_counts = await self._get_entity_counts(template_id)
        total_entities = sum(entity_counts.values())
        
        # Delete template (cascade will delete entities)
        await self.session.delete(template)
        await self.session.commit()
        
        logger.info(
            "template_deleted",
            template_id=str(template_id),
            entities_removed=total_entities
        )
        
        return {
            "deleted": True,
            "entities_removed": total_entities,
            "instances_affected": deployment_count if force else 0
        }
    
    async def export_template(self, template_id: UUID) -> bytes:
        """Export template to ZIP bytes."""
        import zipfile
        from io import BytesIO
        import json
        
        template = await self.get_by_id(template_id)
        if not template:
            raise ValueError("Template not found")
        
        # Get all entities
        result = await self.session.execute(
            select(TemplateEntity)
            .where(TemplateEntity.template_id == template_id)
            .order_by(TemplateEntity.entity_type, TemplateEntity.display_order)
        )
        entities = result.scalars().all()
        
        # Build ZIP
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add manifest
            zf.writestr("template.json", json.dumps(template.manifest_json, indent=2))
            
            # Add entities
            for entity in entities:
                folder = f"{entity.entity_type}s"
                filename = f"{entity.entity_key}.json"
                zf.writestr(
                    f"{folder}/{filename}",
                    json.dumps(entity.entity_data, indent=2)
                )
        
        return buffer.getvalue()
```

**Step 2: Write basic tests**

```python
"""Tests for template service."""

import json
import zipfile
from io import BytesIO
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Template, TemplateEntity
from services.template_service import TemplateService


class TestTemplateService:
    """Test template service functionality."""
    
    @pytest.fixture
    def service(self, db_session: AsyncSession):
        """Create template service with test session."""
        return TemplateService(db_session)
    
    def _create_test_zip(self, slug: str = "test-template") -> bytes:
        """Create a test template ZIP."""
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            manifest = {
                "spec_version": "1.0",
                "template": {
                    "slug": slug,
                    "name": "Test Template",
                    "version": "1.0.0",
                    "category": "test"
                },
                "entities": {
                    "agents": {
                        "count": 1,
                        "files": ["test-agent.json"]
                    },
                    "skills": {"count": 0, "files": []},
                    "tools": {"count": 0, "files": []}
                }
            }
            zf.writestr("template.json", json.dumps(manifest))
            
            agent = {
                "entity_type": "agent",
                "entity_key": "test-agent",
                "name": "Test Agent",
                "description": "A test agent"
            }
            zf.writestr("agents/test-agent.json", json.dumps(agent))
        
        return buffer.getvalue()
    
    async def test_import_template(self, service: TemplateService):
        """Test importing a template."""
        zip_content = self._create_test_zip()
        result = await service.import_template(zip_content)
        
        assert result["slug"] == "test-template"
        assert result["name"] == "Test Template"
        assert result["entities_imported"]["agents"] == 1
        assert result["template_id"] is not None
    
    async def test_import_duplicate_slug(self, service: TemplateService):
        """Test importing template with duplicate slug fails."""
        zip_content = self._create_test_zip()
        await service.import_template(zip_content)
        
        with pytest.raises(ValueError) as exc_info:
            await service.import_template(zip_content)
        
        assert "already exists" in str(exc_info.value)
    
    async def test_get_by_slug(self, service: TemplateService):
        """Test retrieving template by slug."""
        zip_content = self._create_test_zip()
        await service.import_template(zip_content)
        
        template = await service.get_by_slug("test-template")
        assert template is not None
        assert template.name == "Test Template"
    
    async def test_list_templates(self, service: TemplateService):
        """Test listing templates."""
        # Import two templates
        zip1 = self._create_test_zip("template-1")
        zip2 = self._create_test_zip("template-2")
        await service.import_template(zip1)
        await service.import_template(zip2)
        
        result = await service.list_templates()
        assert result["total"] == 2
        assert len(result["templates"]) == 2
```

**Step 3: Run tests**

```bash
PYTHONPATH=. .venv/bin/pytest backend/tests/services/test_template_service.py -v
```

Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/services/template_service.py backend/tests/services/test_template_service.py
git commit -m "feat(23-07): add Template import and management service"
```

---

### Task 8: Create Admin Template API Routes

**Files:**
- Create: `backend/api/routes/admin/templates.py`
- Create: `backend/tests/api/test_admin_templates.py`

**Step 1: Write the API routes**

```python
"""Admin template management API routes."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from core.schemas import (
    TemplateResponse,
    TemplateListResponse,
    TemplateDetailResponse,
    TemplateUpdate,
    TemplateImportResponse,
)
from security.deps import require_admin
from services.template_service import TemplateService

router = APIRouter(prefix="/admin/templates", tags=["admin-templates"])


@router.post(
    "/import",
    response_model=TemplateImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import template from ZIP file"
)
async def import_template(
    file: UploadFile = File(..., description="Template ZIP file"),
    session: AsyncSession = Depends(get_async_session),
    user = Depends(require_admin)
):
    """Import a new template from a ZIP file.
    
    The ZIP must contain:
    - template.json: Manifest file with metadata
    - agents/*.json: Agent definitions
    - skills/*.json: Skill definitions  
    - tools/*.json: Tool definitions
    """
    # Validate file type
    if not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a ZIP archive"
        )
    
    # Read file content
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty"
        )
    
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 50MB limit"
        )
    
    # Import template
    service = TemplateService(session)
    
    try:
        result = await service.import_template(content)
        return TemplateImportResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to import template: {str(e)}"
        )


@router.get(
    "",
    response_model=dict,
    summary="List all templates"
)
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_async_session),
    user = Depends(require_admin)
):
    """List all templates with optional filters and pagination."""
    service = TemplateService(session)
    result = await service.list_templates(
        category=category,
        status=status,
        page=page,
        limit=limit
    )
    
    return result


@router.get(
    "/{template_id}",
    response_model=TemplateDetailResponse,
    summary="Get template details"
)
async def get_template(
    template_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user = Depends(require_admin)
):
    """Get detailed information about a specific template."""
    service = TemplateService(session)
    template = await service.get_by_id(template_id)
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    # Build detailed response
    entity_counts = await service._get_entity_counts(template_id)
    
    # Get entities organized by type
    from sqlalchemy import select
    from core.models import TemplateEntity
    
    result = await session.execute(
        select(TemplateEntity).where(TemplateEntity.template_id == template_id)
    )
    entities = result.scalars().all()
    
    entities_by_type = {"agents": [], "skills": [], "tools": []}
    for entity in entities:
        entity_summary = {
            "entity_key": entity.entity_key,
            "name": entity.entity_data.get("name", ""),
            "description": entity.entity_data.get("description", ""),
            "tags": entity.tags or []
        }
        entities_by_type[entity.entity_type + "s"].append(entity_summary)
    
    return TemplateDetailResponse(
        id=template.id,
        slug=template.slug,
        name=template.name,
        description=template.description,
        version=template.version,
        category=template.category,
        manifest=template.manifest_json,
        is_system=template.is_system,
        status=template.status,
        created_at=template.created_at,
        updated_at=template.updated_at,
        entity_counts=entity_counts,
        entities=entities_by_type
    )


@router.patch(
    "/{template_id}/status",
    response_model=TemplateResponse,
    summary="Update template status"
)
async def update_template_status(
    template_id: UUID,
    update_data: TemplateUpdate,
    session: AsyncSession = Depends(get_async_session),
    user = Depends(require_admin)
):
    """Update template status (enable/disable)."""
    service = TemplateService(session)
    
    # Only allow status updates through this endpoint
    if update_data.status is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only status field can be updated"
        )
    
    template = await service.update_template(template_id, update_data)
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    entity_counts = await service._get_entity_counts(template_id)
    
    return TemplateResponse(
        id=template.id,
        slug=template.slug,
        name=template.name,
        description=template.description,
        version=template.version,
        category=template.category,
        manifest=template.manifest_json,
        is_system=template.is_system,
        status=template.status,
        created_at=template.created_at,
        updated_at=template.updated_at,
        entity_counts=entity_counts
    )


@router.delete(
    "/{template_id}",
    summary="Delete template"
)
async def delete_template(
    template_id: UUID,
    force: bool = Query(False, description="Force delete even if deployed"),
    session: AsyncSession = Depends(get_async_session),
    user = Depends(require_admin)
):
    """Delete a template and all its entities.
    
    By default, will not delete templates with active deployments.
    Set force=true to override this check.
    """
    service = TemplateService(session)
    
    try:
        result = await service.delete_template(template_id, force=force)
        return result
    except ValueError as e:
        if "active deployments" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get(
    "/{template_id}/export",
    summary="Export template to ZIP"
)
async def export_template(
    template_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user = Depends(require_admin)
):
    """Export a template to a downloadable ZIP file."""
    from fastapi.responses import StreamingResponse
    from io import BytesIO
    
    service = TemplateService(session)
    
    try:
        zip_content = await service.export_template(template_id)
        
        # Get template name for filename
        template = await service.get_by_id(template_id)
        filename = f"{template.slug}-v{template.version}.zip"
        
        return StreamingResponse(
            BytesIO(zip_content),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
```

**Step 2: Add routes to main app**

Modify: `backend/api/routes/admin/__init__.py`

```python
from fastapi import APIRouter

# Import all admin routes
from api.routes.admin import templates  # Add this line

router = APIRouter(prefix="/admin")

# Include all admin sub-routers
router.include_router(templates.router)  # Add this line
```

**Step 3: Write API tests**

```python
"""Tests for admin template API routes."""

import json
import zipfile
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


class TestAdminTemplatesAPI:
    """Test admin template API endpoints."""
    
    def _create_template_zip(self) -> BytesIO:
        """Create a test template ZIP."""
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            manifest = {
                "spec_version": "1.0",
                "template": {
                    "slug": "test-template",
                    "name": "Test Template",
                    "version": "1.0.0",
                    "category": "test"
                },
                "entities": {
                    "agents": {"count": 1, "files": ["test-agent.json"]},
                    "skills": {"count": 0, "files": []},
                    "tools": {"count": 0, "files": []}
                }
            }
            zf.writestr("template.json", json.dumps(manifest))
            
            agent = {
                "entity_type": "agent",
                "entity_key": "test-agent",
                "name": "Test Agent",
                "description": "A test agent"
            }
            zf.writestr("agents/test-agent.json", json.dumps(agent))
        
        buffer.seek(0)
        return buffer
    
    async def test_import_template(self, async_client: AsyncClient, admin_token: str):
        """Test importing a template."""
        zip_buffer = self._create_template_zip()
        
        response = await async_client.post(
            "/api/admin/templates/import",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("test.zip", zip_buffer, "application/zip")}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["slug"] == "test-template"
        assert data["entities_imported"]["agents"] == 1
    
    async def test_import_invalid_file_type(self, async_client: AsyncClient, admin_token: str):
        """Test importing non-ZIP file fails."""
        response = await async_client.post(
            "/api/admin/templates/import",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("test.txt", BytesIO(b"not a zip"), "text/plain")}
        )
        
        assert response.status_code == 400
        assert "ZIP" in response.json()["detail"]
    
    async def test_list_templates(self, async_client: AsyncClient, admin_token: str):
        """Test listing templates."""
        # First import a template
        zip_buffer = self._create_template_zip()
        await async_client.post(
            "/api/admin/templates/import",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("test.zip", zip_buffer, "application/zip")}
        )
        
        # List templates
        response = await async_client.get(
            "/api/admin/templates",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["templates"]) >= 1
```

**Step 4: Commit**

```bash
git add backend/api/routes/admin/templates.py backend/api/routes/admin/__init__.py backend/tests/api/test_admin_templates.py
git commit -m "feat(23-08): add Admin Template API routes"
```

---

## Summary

This implementation plan covers **Phase 1 (Foundation)** and **Phase 2 (Admin API)** of the Template System:

**Phase 1: Foundation (6 tasks)**
1. ✅ Template table migration
2. ✅ TemplateEntity table migration  
3. ✅ TemplateInstance and TemplateUserAssignment tables + origin tracking
4. ✅ SQLAlchemy models
5. ✅ Pydantic schemas
6. ✅ ZIP parser service with tests

**Phase 2: Admin API (2 tasks shown, more to come)**
7. ✅ Template import/management service
8. ✅ Admin API routes (import, list, get, update, delete, export)

**Remaining phases:**
- Phase 3: Deployment Engine
- Phase 4: User Gallery  
- Phase 5: Marketing Template
- Phase 6: Polish & Integration

**Next Steps:**
1. Continue with Task 9: Create Deployment Service
2. Continue with Task 10: Create User Gallery API
3. Continue with Task 11-18: Frontend UI components
4. Continue with Task 19-24: Marketing Template definition and packaging

**Files Created:**
- `backend/alembic/versions/032_template_tables.py`
- `backend/core/models/template.py`
- `backend/core/schemas/template.py`
- `backend/services/template_parser.py`
- `backend/services/template_service.py`
- `backend/api/routes/admin/templates.py`
- Plus corresponding test files

**Total Lines of Code:** ~2,000+ lines of Python

---

*Plan Version: 1.0*  
*Created: 2026-03-15*  
*Status: Ready for Implementation*
