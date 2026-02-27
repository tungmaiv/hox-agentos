"""
Pydantic v2 schemas for the workflow subsystem.

WorkflowCreate and WorkflowUpdate enforce schema_version == "1.0" at validation time.
This is a project-wide invariant: definition_json always carries schema_version so
canvas migrations can detect and handle schema changes without downtime.

WorkflowTriggerCreate validates trigger_type to "cron" or "webhook" only.
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    definition_json: dict[str, Any]

    @field_validator("definition_json")
    @classmethod
    def require_schema_version(cls, v: dict[str, Any]) -> dict[str, Any]:
        if v.get("schema_version") != "1.0":
            raise ValueError("definition_json must have schema_version: '1.0'")
        return v


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    definition_json: dict[str, Any] | None = None

    @field_validator("definition_json")
    @classmethod
    def require_schema_version(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is not None and v.get("schema_version") != "1.0":
            raise ValueError("definition_json must have schema_version: '1.0'")
        return v


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    owner_user_id: uuid.UUID | None
    name: str
    description: str | None
    definition_json: dict[str, Any]
    is_template: bool
    template_source_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowListItem(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_template: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowRunResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    owner_user_id: uuid.UUID
    trigger_type: str
    status: str
    checkpoint_id: str | None
    started_at: datetime
    completed_at: datetime | None
    result_json: dict[str, Any] | None

    model_config = {"from_attributes": True}


class PendingHitlResponse(BaseModel):
    count: int


class WorkflowTriggerCreate(BaseModel):
    trigger_type: str  # cron | webhook
    cron_expression: str | None = None
    is_active: bool = True

    @field_validator("trigger_type")
    @classmethod
    def validate_trigger_type(cls, v: str) -> str:
        if v not in ("cron", "webhook"):
            raise ValueError("trigger_type must be 'cron' or 'webhook'")
        return v


class WorkflowTriggerResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    trigger_type: str
    cron_expression: str | None
    webhook_secret: str | None
    is_active: bool

    model_config = {"from_attributes": True}
