"""
SQLAlchemy ORM models for the workflow subsystem.

Three tables:
  - workflows: canvas workflow definitions (owner_user_id NULLABLE for templates)
  - workflow_runs: execution history + state snapshots
  - workflow_triggers: cron + webhook trigger config

Isolation rule: every workflow query MUST include WHERE owner_user_id=$1 from JWT.
Templates have owner_user_id=NULL and are served via a dedicated templates endpoint.

CRITICAL: No FK constraint on owner_user_id columns — users live in Keycloak,
not PostgreSQL. User identity is validated at Gate 1 (JWT), not at DB level.
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base

# JSON type that works in both SQLite (tests) and PostgreSQL (production).
# SQLite cannot compile JSONB natively — use JSON().with_variant(JSONB(), "postgresql")
# following the same pattern as SystemConfig.value.
_JSONB = JSON().with_variant(JSONB(), "postgresql")


class Workflow(Base):
    """
    A saved workflow definition.

    owner_user_id is NULLABLE so template rows (is_template=True) can be inserted
    with owner_user_id=NULL. Regular user workflows always have owner_user_id set.

    definition_json must always contain schema_version: "1.0" (enforced at the
    Pydantic schema layer — WorkflowCreate/WorkflowUpdate validators).
    """

    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition_json: Mapped[dict[str, Any]] = mapped_column(_JSONB, nullable=False)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    template_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkflowRun(Base):
    """
    An execution instance of a workflow.

    Status lifecycle: pending → running → paused_hitl → completed | failed

    checkpoint_id links to a LangGraph checkpoint for resume-after-HITL.
    """

    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False, index=True
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # pending | running | paused_hitl | completed | failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    checkpoint_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    result_json: Mapped[dict[str, Any] | None] = mapped_column(_JSONB, nullable=True)


class WorkflowTrigger(Base):
    """
    A trigger configuration for a workflow — either a cron schedule or a webhook.

    webhook_secret is generated server-side (secrets.token_urlsafe(32)) when
    trigger_type == "webhook". It is never returned to the frontend in plaintext.
    """

    __tablename__ = "workflow_triggers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False, index=True
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)  # cron | webhook
    cron_expression: Mapped[str | None] = mapped_column(String(100), nullable=True)
    webhook_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
