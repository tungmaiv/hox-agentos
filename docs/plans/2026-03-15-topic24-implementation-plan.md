# Topic #24: Third-Party Apps UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Build a complete Third-Party Apps UI system that auto-generates dynamic forms for connected integrations (MCP, API, CLI-Anything) using A2UI, with chat-based customization and form persistence.

**Architecture:** Approach C - Auto-generate forms with A2UI + Chat-based customization using useHumanInTheLoop. Leverages existing CopilotKit infrastructure (A2UIMessageRenderer, AG-UI streaming). Two LangGraph agents (Form Generator + Form Customizer) create and modify A2UI specs stored in PostgreSQL JSONB.

**Tech Stack:** FastAPI, LangGraph, Pydantic, PostgreSQL, SQLAlchemy, CopilotKit, A2UI, React/Next.js, TypeScript

**Design Document:** [docs/enhancement/topics/24-third-party-apps-ui/00-specification.md](../enhancement/topics/24-third-party-apps-ui/00-specification.md)

---

## Phase 1: Foundation - Database & Models (Tasks 1-5)

### Task 1: Create app_form Migration

**Files:**
- Create: `backend/alembic/versions/033_add_app_form_table.py`

**Step 1: Generate migration**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
.venv/bin/alembic revision -m "033_add_app_form_table"
```

**Step 2: Write migration**

```python
"""033_add_app_form_table

Revision ID: 033_add_app_form_table
Revises: 032_template_tables
Create Date: 2026-03-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '033_add_app_form_table'
down_revision = '032_template_tables'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'app_form',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('integration_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('a2ui_spec', postgresql.JSONB, nullable=False),
        sa.Column('form_config', postgresql.JSONB, server_default='{}'),
        sa.Column('execution_config', postgresql.JSONB, server_default='{}'),
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('is_system_generated', sa.Boolean, server_default='false'),
        sa.Column('is_shared', sa.Boolean, server_default='false'),
        sa.Column('usage_count', sa.Integer, server_default='0'),
        sa.Column('last_used_at', sa.DateTime),
        sa.Column('version', sa.Integer, server_default='1'),
        sa.Column('parent_form_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('app_form.id')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('company_id', 'slug'),
        sa.UniqueConstraint('integration_id', 'slug')
    )
    
    # Indexes
    op.create_index('idx_app_form_integration', 'app_form', ['integration_id'])
    op.create_index('idx_app_form_company', 'app_form', ['company_id'])
    op.create_index('idx_app_form_owner', 'app_form', ['owner_user_id'])
    op.create_index('idx_app_form_status', 'app_form', ['status'])
    op.create_index('idx_app_form_system', 'app_form', ['is_system_generated'])


def downgrade():
    op.drop_index('idx_app_form_system', table_name='app_form')
    op.drop_index('idx_app_form_status', table_name='app_form')
    op.drop_index('idx_app_form_owner', table_name='app_form')
    op.drop_index('idx_app_form_company', table_name='app_form')
    op.drop_index('idx_app_form_integration', table_name='app_form')
    op.drop_table('app_form')
```

**Step 3: Run migration**

```bash
cd /home/tungmv/Projects/hox-agentos
just migrate
```

Expected: Migration applies successfully

**Step 4: Commit**

```bash
git add backend/alembic/versions/033_add_app_form_table.py
git commit -m "feat(24-01): add app_form table migration"
```

---

### Task 2: Create AppForm SQLAlchemy Model

**Files:**
- Create: `backend/core/models/app_form.py`
- Modify: `backend/core/models/__init__.py`

**Step 1: Create the model**

```python
"""AppForm SQLAlchemy model."""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class AppForm(Base):
    """Stores A2UI form specifications for third-party app integrations."""
    __tablename__ = "app_form"
    
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    
    # References
    integration_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    company_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    
    # Form metadata
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # A2UI specification
    a2ui_spec: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    
    # Configuration
    form_config: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    execution_config: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="active")
    is_system_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Usage tracking
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Versioning
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_form_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("app_form.id"))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    parent_form: Mapped[Optional["AppForm"]] = relationship("AppForm", remote_side=[id], backref="child_forms")
    
    __table_args__ = (
        UniqueConstraint("company_id", "slug"),
        UniqueConstraint("integration_id", "slug"),
        Index("idx_app_form_integration", "integration_id"),
        Index("idx_app_form_company", "company_id"),
        Index("idx_app_form_owner", "owner_user_id"),
        Index("idx_app_form_status", "status"),
        Index("idx_app_form_system", "is_system_generated"),
    )
```

**Step 2: Add to __init__.py**

```python
# backend/core/models/__init__.py
from core.models.app_form import AppForm

__all__ = [
    # ... existing exports ...
    "AppForm",
]
```

**Step 3: Verify import**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/python -c "from core.models import AppForm; print('AppForm imported successfully')"
```

Expected: `AppForm imported successfully`

**Step 4: Commit**

```bash
git add backend/core/models/app_form.py backend/core/models/__init__.py
git commit -m "feat(24-02): add AppForm SQLAlchemy model"
```

---

### Task 3: Create A2UI Schema Pydantic Models

**Files:**
- Create: `backend/core/schemas/a2ui.py`
- Modify: `backend/core/schemas/__init__.py`

**Step 1: Create A2UI schemas**

```python
"""A2UI (Agent-to-User Interface) schema definitions."""

from typing import Optional, List, Dict, Any, Literal, Union
from pydantic import BaseModel, Field


# ============== Base Components ==============

class ValidationRule(BaseModel):
    """Validation rule for form fields."""
    type: Literal["required", "minLength", "maxLength", "min", "max", 
                   "pattern", "email", "url", "custom", "future_date"]
    message: str
    value: Optional[Any] = None
    customFunction: Optional[str] = None


class A2UIAction(BaseModel):
    """Action button configuration."""
    type: Literal["submit", "button", "reset"]
    label: str
    variant: Optional[Literal["primary", "secondary", "outline", "danger", "ghost"]] = "primary"
    size: Optional[Literal["sm", "md", "lg"]] = "md"
    icon: Optional[str] = None
    disabled: Optional[bool] = False
    action: Optional[str] = None  # Custom action ID
    confirmation: Optional[Dict[str, str]] = None  # {title, message}


# ============== Form Components ==============

class BaseComponent(BaseModel):
    """Base class for all A2UI components."""
    id: str
    label: str
    required: Optional[bool] = False
    disabled: Optional[bool] = False
    placeholder: Optional[str] = None
    helpText: Optional[str] = None
    validation: Optional[List[ValidationRule]] = None
    width: Optional[Literal["full", "half", "third", "quarter"]] = "full"


class TextInputComponent(BaseComponent):
    """Text input field."""
    type: Literal["text-input"] = "text-input"
    minLength: Optional[int] = None
    maxLength: Optional[int] = None
    pattern: Optional[str] = None
    defaultValue: Optional[str] = None


class NumberInputComponent(BaseComponent):
    """Number input field."""
    type: Literal["number-input"] = "number-input"
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    defaultValue: Optional[float] = None


class SelectOption(BaseModel):
    """Option for select/multi-select."""
    value: Union[str, int, float]
    label: str
    disabled: Optional[bool] = False
    group: Optional[str] = None


class SelectComponent(BaseComponent):
    """Dropdown select field."""
    type: Literal["select"] = "select"
    options: List[SelectOption]
    defaultValue: Optional[Union[str, int, float]] = None
    searchable: Optional[bool] = False
    creatable: Optional[bool] = False


class MultiSelectComponent(BaseComponent):
    """Multi-select field."""
    type: Literal["multi-select"] = "multi-select"
    options: List[SelectOption]
    defaultValue: Optional[List[Union[str, int, float]]] = None
    maxSelections: Optional[int] = None
    minSelections: Optional[int] = None


class DatePickerComponent(BaseComponent):
    """Date picker field."""
    type: Literal["date-picker"] = "date-picker"
    minDate: Optional[str] = None  # ISO date
    maxDate: Optional[str] = None
    defaultValue: Optional[str] = None
    showTime: Optional[bool] = False
    dateFormat: Optional[str] = "YYYY-MM-DD"


class TextareaComponent(BaseComponent):
    """Textarea field."""
    type: Literal["textarea"] = "textarea"
    minLength: Optional[int] = None
    maxLength: Optional[int] = None
    rows: Optional[int] = 4
    defaultValue: Optional[str] = None


class CheckboxComponent(BaseComponent):
    """Checkbox field."""
    type: Literal["checkbox"] = "checkbox"
    defaultValue: Optional[bool] = False


class RadioGroupComponent(BaseComponent):
    """Radio button group."""
    type: Literal["radio-group"] = "radio-group"
    options: List[SelectOption]
    defaultValue: Optional[Union[str, int, float]] = None
    layout: Optional[Literal["horizontal", "vertical"]] = "vertical"


class TableColumn(BaseModel):
    """Column definition for table component."""
    key: str
    label: str
    type: Optional[Literal["text", "number", "currency", "date", "badge", "action"]] = "text"
    width: Optional[str] = None
    sortable: Optional[bool] = False
    filterable: Optional[bool] = False


class TableComponent(BaseComponent):
    """Data table component."""
    type: Literal["table"] = "table"
    columns: List[TableColumn]
    dataSource: Literal["static", "dynamic"] = "dynamic"
    data: Optional[List[Dict[str, Any]]] = None
    dataKey: Optional[str] = None
    pagination: Optional[Dict[str, Any]] = None  # {enabled, pageSize}
    selection: Optional[Dict[str, Any]] = None  # {enabled, mode}


class ChartComponent(BaseComponent):
    """Chart component."""
    type: Literal["chart"] = "chart"
    chartType: Literal["bar", "line", "pie", "area", "donut"]
    dataSource: Literal["static", "dynamic"] = "dynamic"
    data: Optional[List[Dict[str, Any]]] = None
    xAxis: Optional[str] = None
    yAxis: Optional[Union[str, List[str]]] = None
    options: Optional[Dict[str, Any]] = None


class SearchComponent(BaseComponent):
    """Search/autocomplete component."""
    type: Literal["search"] = "search"
    searchEndpoint: str
    searchParam: str = "q"
    resultLabelField: str
    resultValueField: str
    debounceMs: Optional[int] = 300
    minQueryLength: Optional[int] = 2


class FileUploadComponent(BaseComponent):
    """File upload component."""
    type: Literal["file-upload"] = "file-upload"
    accept: Optional[List[str]] = None  # MIME types
    maxSize: Optional[int] = None  # Bytes
    maxFiles: Optional[int] = 1
    multiple: Optional[bool] = False


# Union type for all components
A2UIComponent = Union[
    TextInputComponent,
    NumberInputComponent,
    SelectComponent,
    MultiSelectComponent,
    DatePickerComponent,
    TextareaComponent,
    CheckboxComponent,
    RadioGroupComponent,
    TableComponent,
    ChartComponent,
    SearchComponent,
    FileUploadComponent,
]


# ============== Form Specification ==============

class A2UIFormSpec(BaseModel):
    """Complete A2UI form specification."""
    type: Literal["form"] = "form"
    id: str
    title: str
    description: Optional[str] = None
    layout: Optional[Literal["vertical", "horizontal", "grid"]] = "vertical"
    components: List[A2UIComponent]
    actions: Optional[List[A2UIAction]] = None
    conditionalVisibility: Optional[Dict[str, Dict[str, Any]]] = None
    theme: Optional[Dict[str, Any]] = None


# ============== API Schemas ==============

class AppFormCreate(BaseModel):
    """Schema for creating a new app form."""
    integration_id: str
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    slug: str = Field(..., max_length=100)
    a2ui_spec: A2UIFormSpec
    form_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    execution_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    parent_form_id: Optional[str] = None


class AppFormUpdate(BaseModel):
    """Schema for updating an app form."""
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    a2ui_spec: Optional[A2UIFormSpec] = None
    form_config: Optional[Dict[str, Any]] = None
    execution_config: Optional[Dict[str, Any]] = None
    status: Optional[Literal["active", "archived", "draft"]] = None
    is_shared: Optional[bool] = None


class AppFormResponse(BaseModel):
    """Schema for app form response."""
    id: str
    integration_id: str
    company_id: str
    owner_user_id: str
    name: str
    description: Optional[str]
    slug: str
    a2ui_spec: A2UIFormSpec
    form_config: Dict[str, Any]
    execution_config: Dict[str, Any]
    status: str
    is_system_generated: bool
    is_shared: bool
    usage_count: int
    last_used_at: Optional[str]
    version: int
    parent_form_id: Optional[str]
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class AppFormListItem(BaseModel):
    """Schema for app form list item."""
    id: str
    name: str
    description: Optional[str]
    slug: str
    is_system_generated: bool
    usage_count: int
    last_used_at: Optional[str]
    created_at: str


class FormExecutionRequest(BaseModel):
    """Schema for form execution request."""
    form_data: Dict[str, Any]


class FormExecutionResponse(BaseModel):
    """Schema for form execution response."""
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None
```

**Step 2: Add to __init__.py**

```python
# backend/core/schemas/__init__.py
from core.schemas.a2ui import (
    A2UIFormSpec,
    A2UIComponent,
    AppFormCreate,
    AppFormUpdate,
    AppFormResponse,
    AppFormListItem,
    FormExecutionRequest,
    FormExecutionResponse,
)

__all__ = [
    # ... existing exports ...
    "A2UIFormSpec",
    "A2UIComponent",
    "AppFormCreate",
    "AppFormUpdate",
    "AppFormResponse",
    "AppFormListItem",
    "FormExecutionRequest",
    "FormExecutionResponse",
]
```

**Step 3: Verify import**

```bash
PYTHONPATH=. .venv/bin/python -c "from core.schemas.a2ui import A2UIFormSpec; print('A2UI schemas imported successfully')"
```

Expected: `A2UI schemas imported successfully`

**Step 4: Commit**

```bash
git add backend/core/schemas/a2ui.py backend/core/schemas/__init__.py
git commit -m "feat(24-03): add A2UI schema Pydantic models"
```

---

### Task 4: Create AppForm Service

**Files:**
- Create: `backend/services/app_form_service.py`
- Create: `backend/tests/services/test_app_form_service.py`

**Step 1: Create the service**

```python
"""AppForm service for managing form specifications."""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import AppForm
from core.schemas import (
    AppFormCreate,
    AppFormUpdate,
    AppFormResponse,
    AppFormListItem,
)


class AppFormService:
    """Service for managing AppForm CRUD operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_form(
        self,
        data: AppFormCreate,
        company_id: UUID,
        owner_user_id: UUID
    ) -> AppForm:
        """Create a new app form."""
        # Check for duplicate slug
        existing = await self.get_by_slug(company_id, data.slug)
        if existing:
            raise ValueError(f"Form with slug '{data.slug}' already exists")
        
        form = AppForm(
            integration_id=UUID(data.integration_id),
            company_id=company_id,
            owner_user_id=owner_user_id,
            name=data.name,
            description=data.description,
            slug=data.slug,
            a2ui_spec=data.a2ui_spec.model_dump(),
            form_config=data.form_config or {},
            execution_config=data.execution_config or {},
            parent_form_id=UUID(data.parent_form_id) if data.parent_form_id else None,
        )
        
        self.session.add(form)
        await self.session.commit()
        await self.session.refresh(form)
        
        return form
    
    async def get_by_id(self, form_id: UUID) -> Optional[AppForm]:
        """Get form by ID."""
        result = await self.session.execute(
            select(AppForm).where(AppForm.id == form_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_slug(self, company_id: UUID, slug: str) -> Optional[AppForm]:
        """Get form by slug within company."""
        result = await self.session.execute(
            select(AppForm)
            .where(AppForm.company_id == company_id)
            .where(AppForm.slug == slug)
        )
        return result.scalar_one_or_none()
    
    async def list_forms(
        self,
        company_id: UUID,
        integration_id: Optional[UUID] = None,
        include_system: bool = True,
        include_saved: bool = True,
        status: Optional[str] = "active"
    ) -> Dict[str, List[AppForm]]:
        """List forms for a company."""
        query = select(AppForm).where(AppForm.company_id == company_id)
        
        if integration_id:
            query = query.where(AppForm.integration_id == integration_id)
        
        if status:
            query = query.where(AppForm.status == status)
        
        result = await self.session.execute(query)
        forms = result.scalars().all()
        
        system_forms = []
        saved_forms = []
        
        for form in forms:
            if form.is_system_generated:
                if include_system:
                    system_forms.append(form)
            else:
                if include_saved:
                    saved_forms.append(form)
        
        return {
            "system_forms": system_forms,
            "saved_forms": saved_forms,
        }
    
    async def update_form(
        self,
        form_id: UUID,
        data: AppFormUpdate,
        user_id: UUID
    ) -> Optional[AppForm]:
        """Update an existing form."""
        form = await self.get_by_id(form_id)
        if not form:
            return None
        
        # Check ownership (or admin)
        if form.owner_user_id != user_id:
            # TODO: Check if user is admin
            raise PermissionError("You don't have permission to update this form")
        
        if data.name is not None:
            form.name = data.name
        if data.description is not None:
            form.description = data.description
        if data.a2ui_spec is not None:
            form.a2ui_spec = data.a2ui_spec.model_dump()
        if data.form_config is not None:
            form.form_config = data.form_config
        if data.execution_config is not None:
            form.execution_config = data.execution_config
        if data.status is not None:
            form.status = data.status
        if data.is_shared is not None:
            form.is_shared = data.is_shared
        
        form.version += 1
        await self.session.commit()
        await self.session.refresh(form)
        
        return form
    
    async def delete_form(self, form_id: UUID, user_id: UUID) -> bool:
        """Delete a form."""
        form = await self.get_by_id(form_id)
        if not form:
            return False
        
        # Check ownership
        if form.owner_user_id != user_id:
            raise PermissionError("You don't have permission to delete this form")
        
        # Don't allow deleting system forms
        if form.is_system_generated:
            raise ValueError("Cannot delete system-generated forms")
        
        await self.session.delete(form)
        await self.session.commit()
        
        return True
    
    async def increment_usage(self, form_id: UUID) -> None:
        """Increment usage counter for a form."""
        form = await self.get_by_id(form_id)
        if form:
            form.usage_count += 1
            form.last_used_at = datetime.utcnow()
            await self.session.commit()
```

**Step 2: Write tests**

```python
"""Tests for AppForm service."""

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import AppForm
from core.schemas.a2ui import AppFormCreate, A2UIFormSpec, TextInputComponent
from services.app_form_service import AppFormService


class TestAppFormService:
    """Test AppForm service functionality."""
    
    @pytest.fixture
    def service(self, db_session: AsyncSession):
        """Create AppForm service with test session."""
        return AppFormService(db_session)
    
    def _create_test_a2ui_spec(self) -> A2UIFormSpec:
        """Create test A2UI spec."""
        return A2UIFormSpec(
            id="test-form",
            title="Test Form",
            components=[
                TextInputComponent(
                    id="name",
                    label="Name",
                    required=True
                )
            ]
        )
    
    async def test_create_form(self, service: AppFormService):
        """Test creating a new form."""
        company_id = uuid4()
        owner_id = uuid4()
        
        data = AppFormCreate(
            integration_id=str(uuid4()),
            name="Test Form",
            slug="test-form",
            a2ui_spec=self._create_test_a2ui_spec()
        )
        
        form = await service.create_form(data, company_id, owner_id)
        
        assert form.name == "Test Form"
        assert form.slug == "test-form"
        assert form.company_id == company_id
        assert form.owner_user_id == owner_id
        assert form.version == 1
    
    async def test_create_duplicate_slug(self, service: AppFormService):
        """Test creating form with duplicate slug fails."""
        company_id = uuid4()
        owner_id = uuid4()
        
        data = AppFormCreate(
            integration_id=str(uuid4()),
            name="Test Form",
            slug="duplicate-slug",
            a2ui_spec=self._create_test_a2ui_spec()
        )
        
        # Create first form
        await service.create_form(data, company_id, owner_id)
        
        # Try to create second with same slug
        with pytest.raises(ValueError) as exc_info:
            await service.create_form(data, company_id, owner_id)
        
        assert "already exists" in str(exc_info.value)
    
    async def test_get_by_slug(self, service: AppFormService):
        """Test retrieving form by slug."""
        company_id = uuid4()
        owner_id = uuid4()
        
        data = AppFormCreate(
            integration_id=str(uuid4()),
            name="Test Form",
            slug="get-by-slug",
            a2ui_spec=self._create_test_a2ui_spec()
        )
        
        created = await service.create_form(data, company_id, owner_id)
        retrieved = await service.get_by_slug(company_id, "get-by-slug")
        
        assert retrieved is not None
        assert retrieved.id == created.id
    
    async def test_list_forms(self, service: AppFormService):
        """Test listing forms."""
        company_id = uuid4()
        owner_id = uuid4()
        integration_id = uuid4()
        
        # Create system form
        system_data = AppFormCreate(
            integration_id=str(integration_id),
            name="System Form",
            slug="system-form",
            a2ui_spec=self._create_test_a2ui_spec()
        )
        system_form = await service.create_form(system_data, company_id, owner_id)
        system_form.is_system_generated = True
        await service.session.commit()
        
        # Create user form
        user_data = AppFormCreate(
            integration_id=str(integration_id),
            name="User Form",
            slug="user-form",
            a2ui_spec=self._create_test_a2ui_spec()
        )
        await service.create_form(user_data, company_id, owner_id)
        
        # List forms
        result = await service.list_forms(company_id, integration_id)
        
        assert len(result["system_forms"]) == 1
        assert len(result["saved_forms"]) == 1
```

**Step 3: Run tests**

```bash
PYTHONPATH=. .venv/bin/pytest backend/tests/services/test_app_form_service.py -v
```

Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/services/app_form_service.py backend/tests/services/test_app_form_service.py
git commit -m "feat(24-04): add AppForm service with CRUD operations"
```

---

### Task 5: Create REST API Routes

**Files:**
- Create: `backend/api/routes/chat_with_apps.py`
- Modify: `backend/api/routes/__init__.py`

**Step 1: Create API routes**

```python
"""Chat with Apps API routes."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from core.schemas import (
    AppFormCreate,
    AppFormUpdate,
    AppFormResponse,
    AppFormListItem,
    FormExecutionRequest,
    FormExecutionResponse,
)
from security.deps import get_current_user
from services.app_form_service import AppFormService

router = APIRouter(prefix="/chat-with-apps", tags=["chat-with-apps"])


@router.get(
    "/integrations",
    response_model=dict,
    summary="Get connected integrations with their forms"
)
async def get_integrations(
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get all connected integrations for the user's company with form counts."""
    # TODO: Get from Topic #21 Integration Registry
    # For now, return mock data
    return {
        "integrations": [
            {
                "id": "integration-id",
                "name": "HubSpot",
                "type": "mcp",
                "status": "connected",
                "icon_url": "/icons/hubspot.svg",
                "default_forms": [],
                "saved_forms_count": 0
            }
        ]
    }


@router.get(
    "/integrations/{integration_id}/forms",
    response_model=dict,
    summary="Get forms for an integration"
)
async def get_integration_forms(
    integration_id: UUID,
    include_system: bool = Query(True),
    include_saved: bool = Query(True),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get all forms (system and saved) for a specific integration."""
    service = AppFormService(session)
    
    # Get company_id from current_user
    company_id = current_user.company_id  # TODO: Get from user context
    
    forms = await service.list_forms(
        company_id=company_id,
        integration_id=integration_id,
        include_system=include_system,
        include_saved=include_saved
    )
    
    return {
        "integration": {"id": str(integration_id)},
        "system_forms": [AppFormListItem.model_validate(f) for f in forms["system_forms"]],
        "saved_forms": [AppFormListItem.model_validate(f) for f in forms["saved_forms"]],
    }


@router.get(
    "/forms/{form_id}",
    response_model=AppFormResponse,
    summary="Get form details"
)
async def get_form(
    form_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get detailed information about a specific form."""
    service = AppFormService(session)
    
    form = await service.get_by_id(form_id)
    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form not found"
        )
    
    # TODO: Check company access
    
    return AppFormResponse.model_validate(form)


@router.post(
    "/forms",
    response_model=AppFormResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new form"
)
async def create_form(
    data: AppFormCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Create a new app form."""
    service = AppFormService(session)
    
    # Get user context
    company_id = current_user.company_id  # TODO
    owner_id = current_user.id  # TODO
    
    try:
        form = await service.create_form(data, company_id, owner_id)
        return AppFormResponse.model_validate(form)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.patch(
    "/forms/{form_id}",
    response_model=AppFormResponse,
    summary="Update form"
)
async def update_form(
    form_id: UUID,
    data: AppFormUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Update an existing form."""
    service = AppFormService(session)
    
    user_id = current_user.id  # TODO
    
    try:
        form = await service.update_form(form_id, data, user_id)
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Form not found"
            )
        return AppFormResponse.model_validate(form)
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.delete(
    "/forms/{form_id}",
    summary="Delete form"
)
async def delete_form(
    form_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Delete a form."""
    service = AppFormService(session)
    
    user_id = current_user.id  # TODO
    
    try:
        deleted = await service.delete_form(form_id, user_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Form not found"
            )
        return {"deleted": True}
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/forms/{form_id}/execute",
    response_model=FormExecutionResponse,
    summary="Execute form (submit)"
)
async def execute_form(
    form_id: UUID,
    request: FormExecutionRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Execute a form by submitting form data to the integration."""
    service = AppFormService(session)
    
    form = await service.get_by_id(form_id)
    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form not found"
        )
    
    # TODO: Execute via Topic #21 Integration Service
    # For now, return mock success
    
    await service.increment_usage(form_id)
    
    return FormExecutionResponse(
        success=True,
        result={"message": "Form executed successfully"},
        execution_time_ms=150
    )


@router.post(
    "/forms/preview",
    summary="Preview form (test without saving)"
)
async def preview_form(
    data: dict,  # Integration ID + A2UI spec + form data
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Preview a form with sample data without saving it."""
    # TODO: Generate preview data based on A2UI spec
    return {
        "preview_data": {},
        "validation_errors": []
    }
```

**Step 2: Add to routes __init__.py**

```python
# backend/api/routes/__init__.py
from api.routes import chat_with_apps

# Include router
router.include_router(chat_with_apps.router)
```

**Step 3: Commit**

```bash
git add backend/api/routes/chat_with_apps.py backend/api/routes/__init__.py
git commit -m "feat(24-05): add Chat with Apps REST API routes"
```

---

## Phase 2: Form Generator Agent (Tasks 6-8)

### Task 6: Create Form Generator Agent State

**Files:**
- Create: `backend/agents/form_generator/types.py`
- Create: `backend/agents/form_generator/state.py`

**Step 1: Create agent types**

```python
"""Types for Form Generator Agent."""

from typing import TypedDict, Optional, List, Dict, Any
from pydantic import BaseModel, Field


class IntegrationCapability(BaseModel):
    """Describes an integration operation/endpoint."""
    name: str
    description: str
    parameters: List[Dict[str, Any]]
    return_type: Optional[str] = None
    examples: Optional[List[Dict[str, Any]]] = None


class IntegrationSchema(BaseModel):
    """Complete integration schema from Topic #21."""
    integration_id: str
    integration_name: str
    integration_type: str  # mcp, rest, cli
    operations: List[IntegrationCapability]
    entities: Optional[List[Dict[str, Any]]] = None


class FormGenerationIntent(BaseModel):
    """Parsed user intent for form generation."""
    action: str  # create, read, update, delete, list
    entity: str  # deals, contacts, tickets, etc.
    filters: Optional[List[Dict[str, Any]]] = None
    fields: Optional[List[str]] = None
    description: str
```

**Step 2: Create agent state**

```python
"""State definitions for Form Generator Agent."""

from typing import TypedDict, Optional, List, Dict, Any
from langchain_core.messages import BaseMessage

from agents.form_generator.types import IntegrationSchema, FormGenerationIntent


class FormGeneratorState(TypedDict):
    """LangGraph state for Form Generator Agent."""
    messages: List[BaseMessage]
    
    # Context
    integration_id: str
    integration_schema: Optional[IntegrationSchema]
    user_intent: Optional[str]
    parsed_intent: Optional[FormGenerationIntent]
    
    # Generation
    generated_form: Optional[Dict[str, Any]]  # A2UI spec
    iteration_count: int
    max_iterations: int
    
    # Control
    next_node: Optional[str]
    error: Optional[str]
    is_complete: bool
```

**Step 3: Commit**

```bash
git add backend/agents/form_generator/types.py backend/agents/form_generator/state.py
git commit -m "feat(24-06): add Form Generator Agent types and state"
```

---

### Task 7: Create Form Generator Agent Nodes

**Files:**
- Create: `backend/agents/form_generator/nodes.py`
- Create: `backend/agents/form_generator/prompts.py`

**Step 1: Create prompts**

```python
"""Prompts for Form Generator Agent."""

FORM_GENERATOR_SYSTEM_PROMPT = """You are the Form Generator Agent for AgentOS. 
You create dynamic forms for third-party app integrations using A2UI (Agent-to-User Interface) specifications.

YOUR CAPABILITIES:
1. Analyze integration schemas (MCP, REST API, CLI)
2. Understand user intentions from natural language
3. Generate appropriate form fields with validation
4. Suggest helpful defaults and options
5. Create preview tables for data listing

A2UI FORM STRUCTURE:
{
  "type": "form",
  "id": "unique-form-id",
  "title": "Form Title",
  "description": "Optional description",
  "components": [
    // Input components: text-input, number-input, select, multi-select, 
    // date-picker, textarea, checkbox, radio-group
    // Display components: table, chart
  ],
  "actions": [
    {"type": "submit", "label": "Submit", "variant": "primary"},
    {"type": "button", "label": "Customize", "action": "enter_customization_mode"}
  ]
}

COMPONENT TYPES:
- text-input: For short text, with minLength/maxLength/pattern validation
- number-input: For numbers, with min/max/step, prefix/suffix
- select: Dropdown with options, can be searchable/creatable
- multi-select: Multiple selection with min/max selections
- date-picker: Date/time selection with min/max dates
- textarea: Long text with rows configuration
- checkbox: Boolean toggle
- radio-group: Single selection from multiple options
- table: Data table with columns, pagination, selection
- chart: Bar/line/pie charts for data visualization

VALIDATION RULES:
- required: Field must have value
- minLength/maxLength: For text fields
- min/max: For number fields
- pattern: Regex pattern for text validation
- email: Email format validation
- future_date: Date must be in the future

WHEN GENERATING FORMS:
- Use the simplest component that fits the data type
- Group related fields together
- Add helpful placeholder text
- Include field validation (required, min/max, patterns)
- For listing operations, include a table component
- For creation operations, focus on input fields
- Add sensible default values where appropriate

Always output valid A2UI JSON that can be rendered by the frontend.
"""

INTENT_ANALYSIS_PROMPT = """Analyze the user's request and extract their intent for form generation.

User Request: {user_request}

Integration Name: {integration_name}
Available Operations: {operations}

Parse the intent into:
1. Action: What does the user want to do? (create, read, update, delete, list)
2. Entity: What type of data? (deals, contacts, tickets, etc.)
3. Filters: Any filtering criteria mentioned?
4. Fields: Specific fields they want to work with?

Output as JSON:
{
  "action": "create",
  "entity": "deals",
  "filters": [...],
  "fields": [...],
  "description": "User wants to create new deals"
}
"""

FORM_GENERATION_PROMPT = """Generate an A2UI form specification based on the user's intent.

User Intent: {intent}

Integration Schema: {schema}

Generate a complete A2UI form that:
1. Matches the user's intent
2. Uses appropriate components for the data types
3. Includes all required fields
4. Adds helpful validation
5. Includes sensible defaults

Output ONLY valid A2UI JSON:
"""
```

**Step 2: Create nodes**

```python
"""LangGraph nodes for Form Generator Agent."""

import json
from typing import Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from agents.form_generator.state import FormGeneratorState
from agents.form_generator.prompts import (
    FORM_GENERATOR_SYSTEM_PROMPT,
    INTENT_ANALYSIS_PROMPT,
    FORM_GENERATION_PROMPT,
)
from core.config import get_llm


llm = get_llm("blitz/master")


async def analyze_intent(state: FormGeneratorState) -> FormGeneratorState:
    """Parse user request to understand what form they need."""
    user_request = state["messages"][-1].content if state["messages"] else ""
    
    prompt = INTENT_ANALYSIS_PROMPT.format(
        user_request=user_request,
        integration_name=state["integration_schema"].integration_name if state["integration_schema"] else "Unknown",
        operations=[op.name for op in state["integration_schema"].operations] if state["integration_schema"] else []
    )
    
    response = await llm.ainvoke(prompt)
    
    try:
        intent = json.loads(response.content)
        state["parsed_intent"] = intent
        state["next_node"] = "generate_form"
    except json.JSONDecodeError:
        state["error"] = "Failed to parse intent"
        state["next_node"] = "error_handler"
    
    return state


async def discover_capabilities(state: FormGeneratorState) -> FormGeneratorState:
    """Fetch integration schema from Topic #21."""
    # TODO: Call Topic #21 Integration Service
    # For now, use mock schema
    
    from agents.form_generator.types import IntegrationSchema, IntegrationCapability
    
    mock_schema = IntegrationSchema(
        integration_id=state["integration_id"],
        integration_name="HubSpot",
        integration_type="mcp",
        operations=[
            IntegrationCapability(
                name="create_deal",
                description="Create a new deal",
                parameters=[
                    {"name": "dealname", "type": "string", "required": True},
                    {"name": "dealstage", "type": "string", "required": True},
                    {"name": "amount", "type": "number", "required": False},
                    {"name": "closedate", "type": "date", "required": False},
                ]
            ),
            IntegrationCapability(
                name="list_deals",
                description="List all deals",
                parameters=[
                    {"name": "limit", "type": "number", "required": False},
                    {"name": "dealstage", "type": "string", "required": False},
                ]
            ),
        ]
    )
    
    state["integration_schema"] = mock_schema
    state["next_node"] = "analyze_intent"
    
    return state


async def generate_form(state: FormGeneratorState) -> FormGeneratorState:
    """Generate A2UI form specification."""
    if not state["parsed_intent"]:
        state["error"] = "No parsed intent available"
        state["next_node"] = "error_handler"
        return state
    
    prompt = FORM_GENERATION_PROMPT.format(
        intent=state["parsed_intent"].model_dump_json(),
        schema=state["integration_schema"].model_dump_json() if state["integration_schema"] else "{}"
    )
    
    messages = [
        SystemMessage(content=FORM_GENERATOR_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ]
    
    response = await llm.ainvoke(messages)
    
    try:
        # Extract JSON from response
        content = response.content
        # Handle code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        a2ui_spec = json.loads(content.strip())
        state["generated_form"] = a2ui_spec
        state["is_complete"] = True
        state["next_node"] = "emit_form"
    except (json.JSONDecodeError, IndexError) as e:
        state["error"] = f"Failed to parse A2UI JSON: {str(e)}"
        state["next_node"] = "error_handler"
    
    return state


async def emit_form(state: FormGeneratorState) -> FormGeneratorState:
    """Emit the generated form via AG-UI."""
    if state["generated_form"]:
        # Add A2UI envelope marker for frontend
        state["messages"].append(
            AIMessage(content=f"---a2ui_JSON---\n{json.dumps(state['generated_form'])}")
        )
    
    return state


async def error_handler(state: FormGeneratorState) -> FormGeneratorState:
    """Handle errors in the generation process."""
    error_msg = state.get("error", "Unknown error")
    
    state["messages"].append(
        AIMessage(content=f"I apologize, but I encountered an error: {error_msg}. Please try describing your request differently.")
    )
    
    state["is_complete"] = True
    return state


async def should_continue(state: FormGeneratorState) -> str:
    """Determine next node in the graph."""
    if state.get("is_complete"):
        return "end"
    
    if state.get("error"):
        return "error_handler"
    
    return state.get("next_node", "end")
```

**Step 3: Commit**

```bash
git add backend/agents/form_generator/prompts.py backend/agents/form_generator/nodes.py
git commit -m "feat(24-07): add Form Generator Agent prompts and nodes"
```

---

### Task 8: Create Form Generator Agent Graph

**Files:**
- Create: `backend/agents/form_generator/graph.py`
- Create: `backend/agents/form_generator/__init__.py`

**Step 1: Create the graph**

```python
"""Form Generator Agent LangGraph definition."""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agents.form_generator.state import FormGeneratorState
from agents.form_generator.nodes import (
    analyze_intent,
    discover_capabilities,
    generate_form,
    emit_form,
    error_handler,
    should_continue,
)


def create_form_generator_graph():
    """Create and return the Form Generator Agent graph."""
    
    # Create graph
    workflow = StateGraph(FormGeneratorState)
    
    # Add nodes
    workflow.add_node("discover_capabilities", discover_capabilities)
    workflow.add_node("analyze_intent", analyze_intent)
    workflow.add_node("generate_form", generate_form)
    workflow.add_node("emit_form", emit_form)
    workflow.add_node("error_handler", error_handler)
    
    # Add edges
    workflow.set_entry_point("discover_capabilities")
    
    workflow.add_conditional_edges(
        "discover_capabilities",
        should_continue,
        {
            "analyze_intent": "analyze_intent",
            "error_handler": "error_handler",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "analyze_intent",
        should_continue,
        {
            "generate_form": "generate_form",
            "error_handler": "error_handler",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "generate_form",
        should_continue,
        {
            "emit_form": "emit_form",
            "error_handler": "error_handler",
            "end": END
        }
    )
    
    workflow.add_edge("emit_form", END)
    workflow.add_edge("error_handler", END)
    
    # Compile with memory saver for state persistence
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


# Global instance
form_generator_graph = create_form_generator_graph()
```

**Step 2: Create __init__.py**

```python
"""Form Generator Agent package."""

from agents.form_generator.graph import form_generator_graph
from agents.form_generator.state import FormGeneratorState

__all__ = ["form_generator_graph", "FormGeneratorState"]
```

**Step 3: Commit**

```bash
git add backend/agents/form_generator/graph.py backend/agents/form_generator/__init__.py
git commit -m "feat(24-08): add Form Generator Agent LangGraph"
```

---

## Summary

This implementation plan covers **Phase 1 (Foundation)** and **Phase 2 (Form Generator Agent)** of the Third-Party Apps UI:

**Phase 1: Foundation (5 tasks)**
1. ✅ Database migration for `app_form` table
2. ✅ SQLAlchemy model with relationships
3. ✅ A2UI Pydantic schemas (12 component types)
4. ✅ AppForm service with CRUD operations
5. ✅ REST API routes

**Phase 2: Form Generator Agent (3 tasks)**
6. ✅ Agent types and state definitions
7. ✅ Agent nodes (analyze, discover, generate)
8. ✅ LangGraph workflow

**Remaining phases:**
- Phase 3: Frontend Core (A2UI Renderer, ChatWithApps page)
- Phase 4: Customization Agent (useHumanInTheLoop)
- Phase 5: Execution Engine (Topic #21 integration)
- Phase 6: Testing & Polish

**Files Created:**
- `backend/alembic/versions/033_add_app_form_table.py`
- `backend/core/models/app_form.py`
- `backend/core/schemas/a2ui.py`
- `backend/services/app_form_service.py`
- `backend/api/routes/chat_with_apps.py`
- `backend/agents/form_generator/` (package)
- Plus corresponding test files

**Total Lines of Code:** ~1,500+ lines of Python

---

*Plan Version: 1.0*  
*Created: 2026-03-15*  
*Status: Ready for Implementation*
