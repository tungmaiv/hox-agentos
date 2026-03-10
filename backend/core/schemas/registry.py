"""
Pydantic v2 schemas for the extensibility registry CRUD APIs.

Covers all artifact types (agents, tools, skills, MCP servers) and their
permission models. SkillDefinitionCreate includes cross-field validation:
instructional skills require instruction_markdown, procedural skills require
procedure_json.
"""
import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

_SKILL_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_SKILL_NAME_MSG = (
    "Skill name must be kebab-case (lowercase, hyphens only), "
    "1-64 characters, no consecutive hyphens"
)


# ---------------------------------------------------------------------------
# Agent schemas
# ---------------------------------------------------------------------------


class AgentDefinitionCreate(BaseModel):
    name: str
    display_name: str | None = None
    description: str | None = None
    version: str = "1.0.0"
    handler_module: str | None = None
    handler_function: str | None = None
    routing_keywords: list[str] | None = None
    config_json: dict[str, Any] | None = None


class AgentDefinitionUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    version: str | None = None
    handler_module: str | None = None
    handler_function: str | None = None
    routing_keywords: list[str] | None = None
    config_json: dict[str, Any] | None = None


class AgentDefinitionResponse(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str | None
    description: str | None
    version: str
    is_active: bool
    status: str
    last_seen_at: datetime | None
    handler_module: str | None
    handler_function: str | None
    routing_keywords: list[Any] | None
    config_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------


class ToolDefinitionCreate(BaseModel):
    name: str
    display_name: str | None = None
    description: str | None = None
    version: str = "1.0.0"
    handler_type: Literal["backend", "mcp", "sandbox"] = "backend"
    handler_module: str | None = None
    handler_function: str | None = None
    mcp_server_id: uuid.UUID | None = None
    mcp_tool_name: str | None = None
    sandbox_required: bool = False
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    handler_code: str | None = None


class ToolDefinitionUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    version: str | None = None
    status: str | None = None
    handler_type: Literal["backend", "mcp", "sandbox"] | None = None
    handler_module: str | None = None
    handler_function: str | None = None
    handler_code: str | None = None
    mcp_server_id: uuid.UUID | None = None
    mcp_tool_name: str | None = None
    sandbox_required: bool | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None


class ToolDefinitionResponse(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str | None
    description: str | None
    version: str
    is_active: bool
    status: str
    last_seen_at: datetime | None
    handler_type: str
    handler_module: str | None
    handler_function: str | None
    handler_code: str | None
    mcp_server_id: uuid.UUID | None
    mcp_tool_name: str | None
    sandbox_required: bool
    input_schema: dict[str, Any] | None
    output_schema: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ToolListItem(BaseModel):
    """Lightweight tool entry for user-facing lists."""

    id: uuid.UUID
    name: str
    display_name: str | None
    description: str | None
    handler_type: str

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Skill schemas
# ---------------------------------------------------------------------------


class SkillDefinitionCreate(BaseModel):
    name: str
    display_name: str | None = None
    description: str | None = None
    version: str = "1.0.0"
    skill_type: Literal["instructional", "procedural"]
    slash_command: str | None = None
    source_type: Literal["builtin", "imported", "user_created"] = "builtin"
    instruction_markdown: str | None = None
    procedure_json: dict[str, Any] | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    # agentskills.io standard fields
    license: str | None = None
    compatibility: str | None = None
    metadata_json: dict[str, Any] | None = None
    allowed_tools: list[str] | None = None
    tags: list[str] | None = None
    category: str | None = None
    source_url: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v) > 64:
            raise ValueError(_SKILL_NAME_MSG)
        if "--" in v:
            raise ValueError(_SKILL_NAME_MSG)
        if not _SKILL_NAME_RE.match(v):
            raise ValueError(_SKILL_NAME_MSG)
        if v.endswith("-"):
            raise ValueError(_SKILL_NAME_MSG)
        return v

    @model_validator(mode="after")
    def validate_skill_content(self) -> "SkillDefinitionCreate":
        """Instructional skills require instruction_markdown; procedural require procedure_json."""
        if self.skill_type == "instructional" and not self.instruction_markdown:
            raise ValueError(
                "Instructional skills must provide instruction_markdown"
            )
        if self.skill_type == "procedural" and not self.procedure_json:
            raise ValueError(
                "Procedural skills must provide procedure_json"
            )
        return self


class SkillDefinitionUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    version: str | None = None
    skill_type: Literal["instructional", "procedural"] | None = None
    slash_command: str | None = None
    source_type: Literal["builtin", "imported", "user_created"] | None = None
    instruction_markdown: str | None = None
    procedure_json: dict[str, Any] | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    # agentskills.io standard fields
    license: str | None = None
    compatibility: str | None = None
    metadata_json: dict[str, Any] | None = None
    allowed_tools: list[str] | None = None
    tags: list[str] | None = None
    category: str | None = None
    source_url: str | None = None


class SkillDefinitionResponse(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str | None
    description: str | None
    version: str
    is_active: bool
    status: str
    last_seen_at: datetime | None
    skill_type: str
    slash_command: str | None
    source_type: str
    instruction_markdown: str | None
    procedure_json: dict[str, Any] | None
    input_schema: dict[str, Any] | None
    output_schema: dict[str, Any] | None
    # agentskills.io standard fields
    license: str | None
    compatibility: str | None
    metadata_json: dict[str, Any] | None
    allowed_tools: list[str] | None
    tags: list[str] | None
    category: str | None
    source_url: str | None
    is_promoted: bool
    security_score: int | None
    security_report: dict[str, Any] | None
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    share_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class SkillListItem(BaseModel):
    """Lightweight skill entry for user-facing lists."""

    id: uuid.UUID
    name: str
    display_name: str | None
    description: str | None
    slash_command: str | None
    usage_count: int = 0
    is_promoted: bool = False
    is_shared: bool = False

    model_config = ConfigDict(from_attributes=True)


class SkillImportRequest(BaseModel):
    """Import a skill from URL or inline content."""

    source_url: str | None = None
    content: str | None = None

    @model_validator(mode="after")
    def require_at_least_one(self) -> "SkillImportRequest":
        if not self.source_url and not self.content:
            raise ValueError("At least one of source_url or content must be provided")
        return self


class SkillReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]
    notes: str | None = None


class SkillRunResponse(BaseModel):
    success: bool
    output: str
    step_outputs: dict[str, Any] | None = None
    failed_step: str | None = None


class SecurityReportResponse(BaseModel):
    score: int
    factors: dict[str, Any]
    recommendation: str


# ---------------------------------------------------------------------------
# Permission schemas
# ---------------------------------------------------------------------------


class ArtifactPermissionRoleEntry(BaseModel):
    """Single role entry within an artifact permission set request."""

    role: str
    allowed: bool


class ArtifactPermissionSet(BaseModel):
    """Set permissions for an artifact (used in PUT/POST per-artifact)."""

    artifact_type: Literal["agent", "tool", "skill", "mcp_server"]
    roles: list[ArtifactPermissionRoleEntry]


class ArtifactPermissionResponse(BaseModel):
    id: uuid.UUID
    artifact_type: str
    artifact_id: uuid.UUID
    role: str
    allowed: bool
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserArtifactPermissionSet(BaseModel):
    """Set a per-user permission override for an artifact."""

    artifact_type: Literal["agent", "tool", "skill", "mcp_server"]
    user_id: uuid.UUID
    allowed: bool


class UserArtifactPermissionResponse(BaseModel):
    id: uuid.UUID
    artifact_type: str
    artifact_id: uuid.UUID
    user_id: uuid.UUID
    allowed: bool
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RolePermissionSet(BaseModel):
    """Set permissions for a role (bulk replace)."""

    permissions: list[str]


class RolePermissionResponse(BaseModel):
    role: str
    permissions: list[str]


class PermissionApplyRequest(BaseModel):
    """Apply pending permissions by their IDs."""

    ids: list[uuid.UUID]


# ---------------------------------------------------------------------------
# MCP server schemas
# ---------------------------------------------------------------------------


class McpServerCreate(BaseModel):
    """Request body for registering a new MCP server."""

    name: str  # unique display name (e.g. "crm", "docs")
    url: str  # HTTP endpoint base URL (e.g. "http://mcp-crm:8001")
    auth_token: str | None = None  # plaintext Bearer token; encrypted before storage


# ---------------------------------------------------------------------------
# Shared / utility schemas
# ---------------------------------------------------------------------------


class StatusUpdate(BaseModel):
    """Manual status change by admin.

    Only allows active/disabled/deprecated. The pending_review and rejected
    statuses are set exclusively by the skill import/review flow
    (SkillImporter + POST /review endpoint) and cannot be set manually.
    """

    status: Literal["active", "disabled", "deprecated"]


class BulkStatusUpdate(BaseModel):
    ids: list[uuid.UUID]
    status: Literal["active", "disabled", "deprecated"]


# ---------------------------------------------------------------------------
# Skill sharing schemas
# ---------------------------------------------------------------------------


class SkillShareRequest(BaseModel):
    """Request body for granting a user access to a skill."""

    user_id: uuid.UUID


class SkillShareEntry(BaseModel):
    """Single share entry — who was granted access and when."""

    user_id: uuid.UUID
    username: str = ""
    email: str = ""
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
