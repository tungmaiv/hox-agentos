# Unified Registry Implementation Plan

## Overview
Consolidate agents, skills, tools, and MCP servers into a single unified registry with simplified CRUD operations and type-specific behaviors via strategy pattern.

## Principles
- **Latest version only** - No complex versioning/activation workflow
- **Unified skills** - Single skill type with optional procedure field
- **Simple but functional** - Full CRUD (Create, Read, Update, Delete, Clone, Test)
- **Strategy pattern** - Type-specific logic in handler classes, not polymorphic tables

---

## Current Architecture Issues

### 1. Inconsistent CRUD Patterns
| Entity | List | Create | View | Edit | Delete | Clone | Test |
|--------|------|--------|------|------|--------|-------|------|
| Agents | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Skills | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Tools | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| MCP Servers | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |

### 2. Over-Engineering
- **Skills**: Two types (instructional/procedural) with different schemas adds complexity
- **Versioning**: Complex activate/deactivate logic for MVP stage
- **Security Scoring**: AST scanning, security reports - premature for 100-user scale
- **ZIP Import/Export**: Complex bundling for simple skill sharing

### 3. Fragmented Registry Pattern
- ToolRegistry: DB-backed with caching
- MCPRegistry: Runtime discovery
- Inconsistent initialization and refresh patterns

### 4. Missing Core Operations
- No dedicated Edit forms (only status toggles)
- No Delete operations (only soft-disable)
- No Clone/Fork from existing
- No Test endpoint before activation

---

## Proposed Solution: Unified Registry

### Core Philosophy
Single registry table, simplified entities, full CRUD, no premature abstraction.

```
┌─────────────────────────────────────────────────────────────┐
│                    UNIFIED REGISTRY                          │
├─────────────────────────────────────────────────────────────┤
│  registry_entries                                            │
│  ───────────────                                            │
│  id (uuid pk)                                               │
│  type (enum: agent|skill|tool|mcp)                          │
│  name (unique per type)                                     │
│  display_name                                               │
│  description                                                │
│  config_json (flexible per type)                            │
│  version (simple semver)                                    │
│  status (active|disabled|draft)                             │
│  owner_id (uuid)                                            │
│  created_at / updated_at                                    │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   Type-Specific           Type-Specific        Type-Specific
   Config Schemas          Handlers              UI Components
   (Pydantic)              (Strategy Pattern)    (Dynamic Forms)
```

**Benefits:**
- Single CRUD pattern for all entities
- Type-specific behavior via strategy pattern, not polymorphic tables
- Simpler frontend: one generic admin component with type-specific field configs
- Easy to add new entity types

---

## 1. Database Schema

### New Table: `registry_entries`

```sql
CREATE TABLE registry_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(20) NOT NULL CHECK (type IN ('agent', 'skill', 'tool', 'mcp_server')),
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200),
    description TEXT,
    
    -- Type-specific config stored as JSONB
    config JSONB NOT NULL DEFAULT '{}',
    
    -- Simple status: draft (editable) -> active (usable) -> disabled
    status VARCHAR(20) NOT NULL DEFAULT 'draft' 
        CHECK (status IN ('draft', 'active', 'disabled')),
    
    -- Ownership
    owner_id UUID NOT NULL,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,  -- Soft delete
    
    -- Constraints
    UNIQUE(type, name),  -- Name unique within type
    CONSTRAINT name_format CHECK (name ~ '^[a-z][a-z0-9_]*$')
);

-- Indexes
CREATE INDEX idx_registry_entries_type ON registry_entries(type);
CREATE INDEX idx_registry_entries_status ON registry_entries(status);
CREATE INDEX idx_registry_entries_owner ON registry_entries(owner_id);
CREATE INDEX idx_registry_entries_config ON registry_entries USING GIN(config);

-- Trigger for updated_at
CREATE TRIGGER update_registry_entries_updated_at
    BEFORE UPDATE ON registry_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### Migration Strategy

```sql
-- 1. Create new table (above)
-- 2. Migrate existing data

-- Agents
INSERT INTO registry_entries (id, type, name, display_name, description, config, status, owner_id, created_at, updated_at)
SELECT 
    id,
    'agent',
    name,
    display_name,
    description,
    jsonb_build_object(
        'handler_module', handler_module,
        'handler_function', handler_function,
        'routing_keywords', routing_keywords,
        'config', config_json
    ),
    CASE 
        WHEN is_active THEN 'active'
        WHEN status = 'disabled' THEN 'disabled'
        ELSE 'draft'
    END,
    COALESCE(created_by, '00000000-0000-0000-0000-000000000000'::UUID),
    created_at,
    updated_at
FROM agent_definitions
WHERE deleted_at IS NULL;

-- Skills (unified - merge instructional/procedural)
INSERT INTO registry_entries (id, type, name, display_name, description, config, status, owner_id, created_at, updated_at)
SELECT 
    id,
    'skill',
    name,
    display_name,
    description,
    jsonb_build_object(
        'slash_command', slash_command,
        'instruction', instruction_markdown,
        'procedure', procedure_json,
        'input_schema', input_schema,
        'output_schema', output_schema,
        'allowed_tools', allowed_tools,
        'category', category,
        'tags', tags
    ),
    CASE 
        WHEN status = 'active' THEN 'active'
        WHEN status = 'disabled' OR status = 'deprecated' THEN 'disabled'
        ELSE 'draft'
    END,
    COALESCE(created_by, '00000000-0000-0000-0000-000000000000'::UUID),
    created_at,
    updated_at
FROM skill_definitions
WHERE deleted_at IS NULL;

-- Tools
INSERT INTO registry_entries (id, type, name, display_name, description, config, status, owner_id, created_at, updated_at)
SELECT 
    id,
    'tool',
    name,
    display_name,
    description,
    jsonb_build_object(
        'handler_type', handler_type,
        'handler_module', handler_module,
        'handler_function', handler_function,
        'mcp_server_id', mcp_server_id,
        'mcp_tool_name', mcp_tool_name,
        'sandbox_required', sandbox_required,
        'input_schema', input_schema,
        'output_schema', output_schema,
        'required_permissions', required_permissions
    ),
    CASE 
        WHEN is_active THEN 'active'
        WHEN status = 'disabled' THEN 'disabled'
        ELSE 'draft'
    END,
    COALESCE(created_by, '00000000-0000-0000-0000-000000000000'::UUID),
    created_at,
    updated_at
FROM tool_definitions
WHERE deleted_at IS NULL;

-- MCP Servers
INSERT INTO registry_entries (id, type, name, display_name, description, config, status, owner_id, created_at, updated_at)
SELECT 
    id,
    'mcp_server',
    name,
    display_name,
    description,
    jsonb_build_object(
        'url', url,
        'auth_token', auth_token,
        'version', version,
        'openapi_spec_url', openapi_spec_url
    ),
    status,
    '00000000-0000-0000-0000-000000000000'::UUID,  -- System-owned
    created_at,
    updated_at
FROM mcp_servers
WHERE deleted_at IS NULL;
```

---

## 2. Backend Implementation

### 2.1 Models

**`backend/core/models/registry_entry.py`**
```python
from enum import Enum
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from core.db import Base

class EntryType(str, Enum):
    AGENT = "agent"
    SKILL = "skill"
    TOOL = "tool"
    MCP_SERVER = "mcp_server"

class EntryStatus(str, Enum):
    DRAFT = "draft"      # Editable, not yet usable
    ACTIVE = "active"    # Usable in production
    DISABLED = "disabled"  # Soft-deleted or deprecated

class RegistryEntry(Base):
    __tablename__ = "registry_entries"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    type = Column(String(20), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    config = Column(JSONB, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default=EntryStatus.DRAFT.value)
    owner_id = Column(PGUUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    __table_args__ = (
        Index('idx_registry_unique_name', 'type', 'name', unique=True),
    )
```

### 2.2 Type-Specific Config Schemas (Pydantic)

**`backend/core/schemas/registry_configs.py`**
```python
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

# Agent Config
class AgentConfig(BaseModel):
    handler_module: str = Field(..., example="agents.email_agent")
    handler_function: str = Field(..., example="run_email_task")
    routing_keywords: List[str] = Field(default_factory=list)
    agent_config: Dict[str, Any] = Field(default_factory=dict)

# Skill Config (unified)
class SkillConfig(BaseModel):
    slash_command: Optional[str] = Field(None, example="email-digest")
    instruction: Optional[str] = Field(None, description="Markdown instructions")
    procedure: Optional[List[Dict[str, Any]]] = Field(None, description="Step-by-step procedure")
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    allowed_tools: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

# Tool Config
class ToolConfig(BaseModel):
    handler_type: str = Field(..., pattern="^(backend|mcp|sandbox)$")
    handler_module: Optional[str] = None
    handler_function: Optional[str] = None
    mcp_server_id: Optional[str] = None
    mcp_tool_name: Optional[str] = None
    sandbox_required: bool = False
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    required_permissions: List[str] = Field(default_factory=list)

# MCP Server Config
class McpServerConfig(BaseModel):
    url: str = Field(..., example="http://mcp-crm:8001/sse")
    auth_token: Optional[str] = Field(None, description="Encrypted auth token")
    version: str = Field(default="1.0.0")
    openapi_spec_url: Optional[str] = None

# Union type for validation
CONFIG_SCHEMAS = {
    "agent": AgentConfig,
    "skill": SkillConfig,
    "tool": ToolConfig,
    "mcp_server": McpServerConfig,
}

def validate_config(entry_type: str, config: dict) -> dict:
    """Validate config against type-specific schema."""
    schema_class = CONFIG_SCHEMAS.get(entry_type)
    if not schema_class:
        raise ValueError(f"Unknown entry type: {entry_type}")
    validated = schema_class(**config)
    return validated.model_dump()
```

### 2.3 Strategy Pattern - Type Handlers

**`backend/registry/handlers/base.py`**
```python
from abc import ABC, abstractmethod
from typing import Dict, Any
from uuid import UUID

class EntryHandler(ABC):
    """Base class for type-specific entry handlers."""
    
    @abstractmethod
    async def validate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate config, return normalized config."""
        pass
    
    @abstractmethod
    async def test(self, entry_id: UUID, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test the entry before activation. Returns test results."""
        pass
    
    @abstractmethod
    async def execute(self, entry_id: UUID, config: Dict[str, Any], 
                     parameters: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """Execute the entry (for skills/tools)."""
        pass
    
    async def on_create(self, entry_id: UUID, config: Dict[str, Any]) -> None:
        """Hook called after creation."""
        pass
    
    async def on_update(self, entry_id: UUID, old_config: Dict[str, Any], 
                       new_config: Dict[str, Any]) -> None:
        """Hook called after update."""
        pass
    
    async def on_delete(self, entry_id: UUID, config: Dict[str, Any]) -> None:
        """Hook called before soft delete."""
        pass
```

**`backend/registry/handlers/agent_handler.py`**
```python
from typing import Dict, Any
from uuid import UUID
from registry.handlers.base import EntryHandler
from core.schemas.registry_configs import AgentConfig

class AgentHandler(EntryHandler):
    async def validate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        validated = AgentConfig(**config)
        return validated.model_dump()
    
    async def test(self, entry_id: UUID, config: Dict[str, Any]) -> Dict[str, Any]:
        try:
            module = __import__(config["handler_module"], fromlist=[config["handler_function"]])
            handler = getattr(module, config["handler_function"])
            return {"success": True, "message": f"Handler {config['handler_function']} found"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def execute(self, entry_id: UUID, config: Dict[str, Any], 
                     parameters: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        raise NotImplementedError("Agents are executed via master_agent routing")
```

**`backend/registry/handlers/skill_handler.py`**
```python
from typing import Dict, Any
from uuid import UUID
from registry.handlers.base import EntryHandler
from core.schemas.registry_configs import SkillConfig

class SkillHandler(EntryHandler):
    async def validate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        validated = SkillConfig(**config)
        if validated.procedure:
            for step in validated.procedure:
                if "type" not in step:
                    raise ValueError("Each procedure step must have a 'type' field")
        return validated.model_dump()
    
    async def test(self, entry_id: UUID, config: Dict[str, Any]) -> Dict[str, Any]:
        errors = []
        if config.get("procedure"):
            for i, step in enumerate(config["procedure"]):
                if step.get("type") == "tool":
                    tool_name = step.get("tool")
                    # Check tool exists
                    if not await tool_exists(tool_name):
                        errors.append(f"Step {i}: Tool '{tool_name}' not found")
        
        return {
            "success": len(errors) == 0,
            "errors": errors,
            "message": "All tools validated" if not errors else f"Found {len(errors)} errors"
        }
    
    async def execute(self, entry_id: UUID, config: Dict[str, Any], 
                     parameters: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        if config.get("procedure"):
            return await execute_skill_procedure(config["procedure"], parameters, user_id)
        else:
            return {
                "type": "instruction",
                "content": config.get("instruction", "No instructions provided")
            }
```

**`backend/registry/handlers/tool_handler.py`**
```python
from typing import Dict, Any
from uuid import UUID
from registry.handlers.base import EntryHandler
from core.schemas.registry_configs import ToolConfig

class ToolHandler(EntryHandler):
    async def validate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        validated = ToolConfig(**config)
        
        if validated.handler_type == "backend":
            if not validated.handler_module or not validated.handler_function:
                raise ValueError("Backend tools require handler_module and handler_function")
        elif validated.handler_type == "mcp":
            if not validated.mcp_server_id or not validated.mcp_tool_name:
                raise ValueError("MCP tools require mcp_server_id and mcp_tool_name")
        
        return validated.model_dump()
    
    async def test(self, entry_id: UUID, config: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if config["handler_type"] == "backend":
                module = __import__(config["handler_module"], fromlist=[config["handler_function"]])
                handler = getattr(module, config["handler_function"])
            elif config["handler_type"] == "mcp":
                await check_mcp_server_health(config["mcp_server_id"])
            
            return {"success": True, "message": "Tool validated successfully"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def execute(self, entry_id: UUID, config: Dict[str, Any], 
                     parameters: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        return await execute_tool(config["name"], parameters, user_id)
```

**`backend/registry/handlers/mcp_server_handler.py`**
```python
from typing import Dict, Any
from uuid import UUID
from registry.handlers.base import EntryHandler
from core.schemas.registry_configs import McpServerConfig

class McpServerHandler(EntryHandler):
    async def validate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        validated = McpServerConfig(**config)
        if not validated.url.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return validated.model_dump()
    
    async def test(self, entry_id: UUID, config: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = await test_server_connection(config["url"], config.get("auth_token"))
            return {"success": True, "message": f"Connected successfully. Available tools: {result.get('tools', [])}"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def execute(self, entry_id: UUID, config: Dict[str, Any], 
                     parameters: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        raise NotImplementedError("MCP servers are not directly executable")
    
    async def on_create(self, entry_id: UUID, config: Dict[str, Any]) -> None:
        await discover_and_register_tools(entry_id, config)
```

**`backend/registry/handlers/__init__.py`**
```python
from registry.handlers.agent_handler import AgentHandler
from registry.handlers.skill_handler import SkillHandler
from registry.handlers.tool_handler import ToolHandler
from registry.handlers.mcp_server_handler import McpServerHandler

HANDLERS = {
    "agent": AgentHandler(),
    "skill": SkillHandler(),
    "tool": ToolHandler(),
    "mcp_server": McpServerHandler(),
}

def get_handler(entry_type: str) -> EntryHandler:
    if entry_type not in HANDLERS:
        raise ValueError(f"Unknown entry type: {entry_type}")
    return HANDLERS[entry_type]
```

### 2.4 Unified Registry Service

**`backend/registry/service.py`**
```python
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.registry_entry import RegistryEntry, EntryStatus
from core.schemas.registry_configs import validate_config
from registry.handlers import get_handler

class RegistryService:
    """Unified service for all registry operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def list_entries(
        self, 
        entry_type: Optional[str] = None,
        status: Optional[str] = None,
        owner_id: Optional[UUID] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[RegistryEntry]:
        """List registry entries with filtering."""
        query = select(RegistryEntry).where(RegistryEntry.deleted_at.is_(None))
        
        if entry_type:
            query = query.where(RegistryEntry.type == entry_type)
        if status:
            query = query.where(RegistryEntry.status == status)
        if owner_id:
            query = query.where(RegistryEntry.owner_id == owner_id)
        if search:
            query = query.where(
                or_(
                    RegistryEntry.name.ilike(f"%{search}%"),
                    RegistryEntry.display_name.ilike(f"%{search}%"),
                    RegistryEntry.description.ilike(f"%{search}%")
                )
            )
        
        query = query.order_by(RegistryEntry.updated_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_entry(self, entry_id: UUID) -> Optional[RegistryEntry]:
        """Get single entry by ID."""
        result = await self.session.execute(
            select(RegistryEntry).where(
                and_(
                    RegistryEntry.id == entry_id,
                    RegistryEntry.deleted_at.is_(None)
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_entry_by_name(self, entry_type: str, name: str) -> Optional[RegistryEntry]:
        """Get entry by type and name."""
        result = await self.session.execute(
            select(RegistryEntry).where(
                and_(
                    RegistryEntry.type == entry_type,
                    RegistryEntry.name == name,
                    RegistryEntry.deleted_at.is_(None)
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def create_entry(
        self,
        entry_type: str,
        name: str,
        display_name: str,
        description: str,
        config: Dict[str, Any],
        owner_id: UUID
    ) -> RegistryEntry:
        """Create new registry entry."""
        handler = get_handler(entry_type)
        validated_config = await handler.validate(config)
        
        entry = RegistryEntry(
            type=entry_type,
            name=name,
            display_name=display_name,
            description=description,
            config=validated_config,
            status=EntryStatus.DRAFT.value,
            owner_id=owner_id
        )
        
        self.session.add(entry)
        await self.session.flush()
        
        await handler.on_create(entry.id, validated_config)
        
        return entry
    
    async def update_entry(
        self,
        entry_id: UUID,
        updates: Dict[str, Any],
        owner_id: UUID
    ) -> RegistryEntry:
        """Update registry entry."""
        entry = await self.get_entry(entry_id)
        if not entry:
            raise ValueError(f"Entry {entry_id} not found")
        
        if entry.owner_id != owner_id:
            raise PermissionError("Not authorized to update this entry")
        
        if entry.status != EntryStatus.DRAFT.value:
            raise ValueError("Can only update entries in draft status. Create new version instead.")
        
        old_config = entry.config.copy()
        
        if "display_name" in updates:
            entry.display_name = updates["display_name"]
        if "description" in updates:
            entry.description = updates["description"]
        if "config" in updates:
            handler = get_handler(entry.type)
            entry.config = await handler.validate(updates["config"])
        
        await self.session.flush()
        
        handler = get_handler(entry.type)
        await handler.on_update(entry_id, old_config, entry.config)
        
        return entry
    
    async def change_status(
        self,
        entry_id: UUID,
        new_status: str,
        owner_id: UUID
    ) -> RegistryEntry:
        """Change entry status (draft -> active -> disabled)."""
        entry = await self.get_entry(entry_id)
        if not entry:
            raise ValueError(f"Entry {entry_id} not found")
        
        if entry.owner_id != owner_id:
            raise PermissionError("Not authorized")
        
        valid_transitions = {
            EntryStatus.DRAFT.value: [EntryStatus.ACTIVE.value, EntryStatus.DISABLED.value],
            EntryStatus.ACTIVE.value: [EntryStatus.DISABLED.value, EntryStatus.DRAFT.value],
            EntryStatus.DISABLED.value: [EntryStatus.DRAFT.value],
        }
        
        if new_status not in valid_transitions.get(entry.status, []):
            raise ValueError(f"Invalid status transition: {entry.status} -> {new_status}")
        
        if new_status == EntryStatus.ACTIVE.value:
            handler = get_handler(entry.type)
            test_result = await handler.test(entry_id, entry.config)
            if not test_result.get("success"):
                raise ValueError(f"Cannot activate: {test_result.get('message')}")
        
        entry.status = new_status
        await self.session.flush()
        
        return entry
    
    async def delete_entry(self, entry_id: UUID, owner_id: UUID) -> None:
        """Soft delete entry."""
        entry = await self.get_entry(entry_id)
        if not entry:
            raise ValueError(f"Entry {entry_id} not found")
        
        if entry.owner_id != owner_id:
            raise PermissionError("Not authorized")
        
        handler = get_handler(entry.type)
        await handler.on_delete(entry_id, entry.config)
        
        entry.deleted_at = datetime.utcnow()
        await self.session.flush()
    
    async def clone_entry(
        self,
        entry_id: UUID,
        new_name: str,
        owner_id: UUID
    ) -> RegistryEntry:
        """Clone existing entry as new draft."""
        source = await self.get_entry(entry_id)
        if not source:
            raise ValueError(f"Entry {entry_id} not found")
        
        return await self.create_entry(
            entry_type=source.type,
            name=new_name,
            display_name=f"{source.display_name} (Copy)",
            description=source.description,
            config=source.config,
            owner_id=owner_id
        )
    
    async def test_entry(self, entry_id: UUID) -> Dict[str, Any]:
        """Test entry without activating."""
        entry = await self.get_entry(entry_id)
        if not entry:
            raise ValueError(f"Entry {entry_id} not found")
        
        handler = get_handler(entry.type)
        return await handler.test(entry_id, entry.config)
```

### 2.5 Unified API Routes

**`backend/api/routes/registry.py`**
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from uuid import UUID

from api.deps import get_current_user, require_permission
from core.schemas.user import UserContext
from registry.service import RegistryService
from api.schemas.registry import (
    RegistryEntryCreate,
    RegistryEntryUpdate,
    RegistryEntryResponse,
    RegistryEntryList,
    TestResult,
    StatusChange
)

router = APIRouter(prefix="/api/registry", tags=["registry"])

@router.get("/entries", response_model=RegistryEntryList)
async def list_entries(
    type: Optional[str] = Query(None, description="Filter by type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in name/display_name/description"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserContext = Depends(get_current_user),
    service: RegistryService = Depends(get_registry_service)
):
    """List registry entries with filtering."""
    entries = await service.list_entries(
        entry_type=type,
        status=status,
        owner_id=current_user.user_id if not current_user.is_admin else None,
        search=search,
        limit=limit,
        offset=offset
    )
    return RegistryEntryList(
        items=[RegistryEntryResponse.from_orm(e) for e in entries],
        total=len(entries)
    )

@router.post("/entries", response_model=RegistryEntryResponse, status_code=201)
async def create_entry(
    data: RegistryEntryCreate,
    current_user: UserContext = Depends(require_permission("registry:create")),
    service: RegistryService = Depends(get_registry_service)
):
    """Create new registry entry."""
    try:
        entry = await service.create_entry(
            entry_type=data.type,
            name=data.name,
            display_name=data.display_name,
            description=data.description,
            config=data.config,
            owner_id=current_user.user_id
        )
        return RegistryEntryResponse.from_orm(entry)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/entries/{entry_id}", response_model=RegistryEntryResponse)
async def get_entry(
    entry_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    service: RegistryService = Depends(get_registry_service)
):
    """Get single entry details."""
    entry = await service.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    if entry.owner_id != current_user.user_id and not current_user.is_admin:
        if entry.status != "active":
            raise HTTPException(status_code=404, detail="Entry not found")
    
    return RegistryEntryResponse.from_orm(entry)

@router.put("/entries/{entry_id}", response_model=RegistryEntryResponse)
async def update_entry(
    entry_id: UUID,
    data: RegistryEntryUpdate,
    current_user: UserContext = Depends(get_current_user),
    service: RegistryService = Depends(get_registry_service)
):
    """Update registry entry (only if in draft status)."""
    try:
        entry = await service.update_entry(
            entry_id=entry_id,
            updates=data.dict(exclude_unset=True),
            owner_id=current_user.user_id
        )
        return RegistryEntryResponse.from_orm(entry)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not authorized")

@router.post("/entries/{entry_id}/status", response_model=RegistryEntryResponse)
async def change_status(
    entry_id: UUID,
    data: StatusChange,
    current_user: UserContext = Depends(get_current_user),
    service: RegistryService = Depends(get_registry_service)
):
    """Change entry status (draft <-> active <-> disabled)."""
    try:
        entry = await service.change_status(
            entry_id=entry_id,
            new_status=data.status,
            owner_id=current_user.user_id
        )
        return RegistryEntryResponse.from_orm(entry)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not authorized")

@router.delete("/entries/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    service: RegistryService = Depends(get_registry_service)
):
    """Soft delete registry entry."""
    try:
        await service.delete_entry(entry_id, current_user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not authorized")

@router.post("/entries/{entry_id}/clone", response_model=RegistryEntryResponse, status_code=201)
async def clone_entry(
    entry_id: UUID,
    new_name: str = Query(..., description="Name for the cloned entry"),
    current_user: UserContext = Depends(get_current_user),
    service: RegistryService = Depends(get_registry_service)
):
    """Clone existing entry as new draft."""
    try:
        entry = await service.clone_entry(entry_id, new_name, current_user.user_id)
        return RegistryEntryResponse.from_orm(entry)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/entries/{entry_id}/test", response_model=TestResult)
async def test_entry(
    entry_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    service: RegistryService = Depends(get_registry_service)
):
    """Test entry without activating."""
    entry = await service.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    if entry.owner_id != current_user.user_id and entry.status != "active":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    result = await service.test_entry(entry_id)
    return TestResult(**result)
```

### 2.6 Request/Response Schemas

**`backend/api/schemas/registry.py`**
```python
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

class RegistryEntryBase(BaseModel):
    type: str = Field(..., description="Entry type: agent|skill|tool|mcp_server")
    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)

class RegistryEntryCreate(RegistryEntryBase):
    pass

class RegistryEntryUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

class RegistryEntryResponse(RegistryEntryBase):
    id: UUID
    status: str
    owner_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class RegistryEntryList(BaseModel):
    items: List[RegistryEntryResponse]
    total: int

class TestResult(BaseModel):
    success: bool
    message: str
    errors: Optional[List[str]] = None
    details: Optional[Dict[str, Any]] = None

class StatusChange(BaseModel):
    status: str = Field(..., pattern=r"^(draft|active|disabled)$")
```

---

## 3. Frontend Implementation

### 3.1 Types

**`frontend/lib/registry-types.ts`**
```typescript
export type EntryType = 'agent' | 'skill' | 'tool' | 'mcp_server';
export type EntryStatus = 'draft' | 'active' | 'disabled';

export interface RegistryEntry {
  id: string;
  type: EntryType;
  name: string;
  display_name: string;
  description?: string;
  config: Record<string, any>;
  status: EntryStatus;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface RegistryEntryCreate {
  type: EntryType;
  name: string;
  display_name: string;
  description?: string;
  config: Record<string, any>;
}

export interface RegistryEntryUpdate {
  display_name?: string;
  description?: string;
  config?: Record<string, any>;
}

export interface TestResult {
  success: boolean;
  message: string;
  errors?: string[];
  details?: Record<string, any>;
}

export interface FieldConfig {
  name: string;
  label: string;
  type: 'text' | 'textarea' | 'select' | 'json' | 'array' | 'boolean';
  required?: boolean;
  options?: { value: string; label: string }[];
  placeholder?: string;
  helpText?: string;
}

export const TYPE_FIELD_CONFIGS: Record<EntryType, FieldConfig[]> = {
  agent: [
    { name: 'handler_module', label: 'Handler Module', type: 'text', required: true, placeholder: 'agents.email_agent' },
    { name: 'handler_function', label: 'Handler Function', type: 'text', required: true, placeholder: 'run_email_task' },
    { name: 'routing_keywords', label: 'Routing Keywords', type: 'array', placeholder: 'email, mail, inbox' },
    { name: 'agent_config', label: 'Agent Config', type: 'json', helpText: 'Additional configuration as JSON' },
  ],
  skill: [
    { name: 'slash_command', label: 'Slash Command', type: 'text', placeholder: 'email-digest' },
    { name: 'instruction', label: 'Instructions', type: 'textarea', placeholder: 'Markdown instructions...' },
    { name: 'procedure', label: 'Procedure Steps', type: 'json', helpText: 'JSON array of steps (optional)' },
    { name: 'input_schema', label: 'Input Schema', type: 'json', helpText: 'JSON Schema for inputs' },
    { name: 'output_schema', label: 'Output Schema', type: 'json', helpText: 'JSON Schema for outputs' },
    { name: 'allowed_tools', label: 'Allowed Tools', type: 'array', placeholder: 'email.send, email.fetch' },
    { name: 'category', label: 'Category', type: 'text' },
    { name: 'tags', label: 'Tags', type: 'array', placeholder: 'productivity, email' },
  ],
  tool: [
    { name: 'handler_type', label: 'Handler Type', type: 'select', required: true, options: [
      { value: 'backend', label: 'Backend Function' },
      { value: 'mcp', label: 'MCP Tool' },
      { value: 'sandbox', label: 'Sandboxed' },
    ]},
    { name: 'handler_module', label: 'Handler Module', type: 'text', placeholder: 'tools.email_tools' },
    { name: 'handler_function', label: 'Handler Function', type: 'text', placeholder: 'send_email' },
    { name: 'mcp_server_id', label: 'MCP Server ID', type: 'text' },
    { name: 'mcp_tool_name', label: 'MCP Tool Name', type: 'text' },
    { name: 'sandbox_required', label: 'Requires Sandbox', type: 'boolean' },
    { name: 'input_schema', label: 'Input Schema', type: 'json' },
    { name: 'output_schema', label: 'Output Schema', type: 'json' },
    { name: 'required_permissions', label: 'Required Permissions', type: 'array' },
  ],
  mcp_server: [
    { name: 'url', label: 'Server URL', type: 'text', required: true, placeholder: 'http://mcp-crm:8001/sse' },
    { name: 'auth_token', label: 'Auth Token', type: 'text' },
    { name: 'version', label: 'Version', type: 'text', placeholder: '1.0.0' },
    { name: 'openapi_spec_url', label: 'OpenAPI Spec URL', type: 'text' },
  ],
};
```

### 3.2 API Client

**`frontend/lib/registry-api.ts`**
```typescript
import { RegistryEntry, RegistryEntryCreate, RegistryEntryUpdate, TestResult, EntryType, EntryStatus } from './registry-types';

const API_BASE = '/api/registry';

export interface ListParams {
  type?: EntryType;
  status?: EntryStatus;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface ListResponse {
  items: RegistryEntry[];
  total: number;
}

export async function listEntries(params: ListParams = {}): Promise<ListResponse> {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) searchParams.append(key, String(value));
  });
  
  const res = await fetch(`${API_BASE}/entries?${searchParams}`);
  if (!res.ok) throw new Error('Failed to fetch entries');
  return res.json();
}

export async function getEntry(id: string): Promise<RegistryEntry> {
  const res = await fetch(`${API_BASE}/entries/${id}`);
  if (!res.ok) throw new Error('Failed to fetch entry');
  return res.json();
}

export async function createEntry(data: RegistryEntryCreate): Promise<RegistryEntry> {
  const res = await fetch(`${API_BASE}/entries`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create entry');
  return res.json();
}

export async function updateEntry(id: string, data: RegistryEntryUpdate): Promise<RegistryEntry> {
  const res = await fetch(`${API_BASE}/entries/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update entry');
  return res.json();
}

export async function changeStatus(id: string, status: EntryStatus): Promise<RegistryEntry> {
  const res = await fetch(`${API_BASE}/entries/${id}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error('Failed to change status');
  return res.json();
}

export async function deleteEntry(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/entries/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete entry');
}

export async function cloneEntry(id: string, newName: string): Promise<RegistryEntry> {
  const res = await fetch(`${API_BASE}/entries/${id}/clone?new_name=${encodeURIComponent(newName)}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to clone entry');
  return res.json();
}

export async function testEntry(id: string): Promise<TestResult> {
  const res = await fetch(`${API_BASE}/entries/${id}/test`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to test entry');
  return res.json();
}
```

### 3.3 React Hook

**`frontend/hooks/use-registry.ts`**
```typescript
'use client';

import { useState, useCallback } from 'react';
import { RegistryEntry, RegistryEntryCreate, RegistryEntryUpdate, EntryType, EntryStatus, TestResult } from '@/lib/registry-types';
import * as api from '@/lib/registry-api';

interface UseRegistryOptions {
  type?: EntryType;
  status?: EntryStatus;
}

export function useRegistry(options: UseRegistryOptions = {}) {
  const [entries, setEntries] = useState<RegistryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchEntries = useCallback(async (search?: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.listEntries({ ...options, search });
      setEntries(response.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [options.type, options.status]);

  const create = async (data: RegistryEntryCreate): Promise<RegistryEntry> => {
    const entry = await api.createEntry(data);
    setEntries(prev => [entry, ...prev]);
    return entry;
  };

  const update = async (id: string, data: RegistryEntryUpdate): Promise<RegistryEntry> => {
    const entry = await api.updateEntry(id, data);
    setEntries(prev => prev.map(e => e.id === id ? entry : e));
    return entry;
  };

  const changeStatus = async (id: string, status: EntryStatus): Promise<RegistryEntry> => {
    const entry = await api.changeStatus(id, status);
    setEntries(prev => prev.map(e => e.id === id ? entry : e));
    return entry;
  };

  const remove = async (id: string): Promise<void> => {
    await api.deleteEntry(id);
    setEntries(prev => prev.filter(e => e.id !== id));
  };

  const clone = async (id: string, newName: string): Promise<RegistryEntry> => {
    const entry = await api.cloneEntry(id, newName);
    setEntries(prev => [entry, ...prev]);
    return entry;
  };

  const test = async (id: string): Promise<TestResult> => {
    return await api.testEntry(id);
  };

  return {
    entries,
    loading,
    error,
    fetchEntries,
    create,
    update,
    changeStatus,
    remove,
    clone,
    test,
  };
}
```

---

## 4. Migration Steps

### Phase 1: Database (1-2 days)
1. Create `registry_entries` table
2. Write migration script to transform existing data
3. Run migration in staging
4. Verify data integrity

### Phase 2: Backend (3-4 days)
1. Create models, schemas, handlers
2. Implement RegistryService
3. Create unified API routes
4. Write tests for all CRUD operations
5. Deprecate old routes (keep for backward compat during transition)

### Phase 3: Frontend (3-4 days)
1. Create new registry types and API client
2. Build new admin page with tabbed interface
3. Implement create/edit/test dialogs
4. Test all operations end-to-end

### Phase 4: Cleanup (1 day)
1. Remove old routes after frontend fully migrated
2. Mark old tables as deprecated
3. Update documentation

---

## 5. Benefits

1. **Simplified Mental Model**: One pattern for all entities
2. **Less Code**: ~60% reduction in LOC (one CRUD pattern vs 4 separate ones)
3. **Consistent UX**: Same UI patterns for all entity types
4. **Easier Testing**: One test suite covers all entity types
5. **Extensible**: Adding new entity type = add handler + field config
6. **Full CRUD**: No more missing edit/delete operations

---

## 6. Trade-offs

| Pros | Cons |
|------|------|
| Simpler codebase | Loses some DB-level type safety |
| Faster development | Migration complexity |
| Consistent patterns | Needs careful handler testing |
| Full CRUD coverage | Frontend needs rebuilding |
| Easy to extend | Breaks existing API (major version bump) |

---

## 7. Files to Create/Modify

### New Files
```
backend/core/models/registry_entry.py
backend/core/schemas/registry_configs.py
backend/registry/
  ├── __init__.py
  ├── service.py
  └── handlers/
      ├── __init__.py
      ├── base.py
      ├── agent_handler.py
      ├── skill_handler.py
      ├── tool_handler.py
      └── mcp_server_handler.py
backend/api/routes/registry.py
backend/api/schemas/registry.py
backend/alembic/versions/XXX_create_registry_entries.py

frontend/lib/registry-types.ts
frontend/lib/registry-api.ts
frontend/hooks/use-registry.ts
frontend/app/(authenticated)/admin/registry/page.tsx
frontend/components/registry/
  ├── registry-list.tsx
  ├── create-entry-dialog.tsx
  ├── edit-entry-dialog.tsx
  └── test-entry-dialog.tsx
```

### Modified Files
```
backend/main.py (add new routes)
backend/core/db.py (add RegistryEntry to Base)
backend/agents/master_agent.py (use new registry)
backend/gateway/tool_registry.py (integrate with new service)

frontend/app/(authenticated)/admin/layout.tsx (add Registry tab)
```

---

## 8. Success Criteria

- [ ] All 4 entity types manageable through unified UI
- [ ] Full CRUD working: Create, Read, Update, Delete, Clone, Test
- [ ] Migration preserves all existing data
- [ ] All existing tests pass
- [ ] New tests cover 80%+ of registry service
- [ ] Frontend build passes
- [ ] No breaking changes to runtime behavior (only API routes change)

---

## 9. Admin Menu Consolidation

### Current State (Problem)
13 fragmented tabs causing cognitive overload:
- Agents, Tools, Skills, MCP Servers, Permissions, Identity, Config, Memory, 
  Credentials, Users, Skill Store, AI Builder, Builder+

### Proposed Structure (4 Main Tabs)

#### **Registry** (Consolidated entity management)
- Agents
- Skills  
- Tools
- MCP Servers
- Skill Store

#### **Access** (Identity & permissions)
- Identity (Keycloak SSO)
- Users (local users/groups)
- Permissions (roles & ACL)

#### **System** (Infrastructure & operations)
- Config (system toggles)
- Memory (reindex management)
- Credentials (OAuth management)

#### **Build** (Development tools)
- AI Builder (single unified builder - merge AI Builder + Builder+)

### Navigation Implementation

**Frontend structure:**
```
frontend/app/(authenticated)/admin/
├── layout.tsx (tab navigation)
├── registry/
│   ├── page.tsx (tabbed sub-nav: Agents/Skills/Tools/MCP/Store)
│   ├── agents/
│   ├── skills/
│   ├── tools/
│   └── mcp-servers/
├── access/
│   ├── page.tsx (tabbed sub-nav: Identity/Users/Permissions)
│   ├── identity/
│   ├── users/
│   └── permissions/
├── system/
│   ├── page.tsx (tabbed sub-nav: Config/Memory/Credentials)
│   ├── config/
│   ├── memory/
│   └── credentials/
└── build/
    └── page.tsx (unified AI builder)
```

**New Files to Create:**
```
frontend/app/(authenticated)/admin/
├── registry/
│   └── page.tsx
├── access/
│   └── page.tsx
├── system/
│   └── page.tsx
└── build/
    └── page.tsx (unified builder merging AI Builder + Builder+)
```

**Modified Files:**
```
frontend/app/(authenticated)/admin/layout.tsx (new 4-tab navigation)
frontend/app/(authenticated)/admin/agents/page.tsx (move to registry/)
frontend/app/(authenticated)/admin/tools/page.tsx (move to registry/)
frontend/app/(authenticated)/admin/skills/page.tsx (move to registry/)
frontend/app/(authenticated)/admin/mcp-servers/page.tsx (move to registry/)
frontend/app/(authenticated)/admin/skill-store/page.tsx (move to registry/)
frontend/app/(authenticated)/admin/permissions/page.tsx (move to access/)
frontend/app/(authenticated)/admin/identity/page.tsx (move to access/)
frontend/app/(authenticated)/admin/users/page.tsx (move to access/)
frontend/app/(authenticated)/admin/config/page.tsx (move to system/)
frontend/app/(authenticated)/admin/memory/page.tsx (move to system/)
frontend/app/(authenticated)/admin/credentials/page.tsx (move to system/)
frontend/app/(authenticated)/admin/create/page.tsx (merge into build/)
frontend/app/(authenticated)/admin/builder/page.tsx (merge into build/)
```

### Benefits
- **75% reduction**: 13 tabs → 4 tabs
- **Logical grouping**: Related features together
- **Scalable**: Easy to add new registry types
- **Role-friendly**: Can hide entire sections by role

### Migration Path
1. Create new layout with 4 tabs
2. Move existing pages to sub-routes
3. Merge AI Builder + Builder+ into unified builder
4. Update navigation links
5. Deprecate old routes (redirect to new locations)
