"""Phase 4 — Workflow tables

To apply this migration:
  just migrate
  (or from host: cd backend && .venv/bin/alembic upgrade head)
  (or via docker: docker exec -it blitz-postgres psql -U blitz blitz -c "...")

Revision ID: 010
Revises: 009
Create Date: 2026-02-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # workflows table
    # IMPORTANT: owner_user_id is NULLABLE so template rows can have owner_user_id=NULL
    # No FK constraint on owner_user_id — users live in Keycloak, not PostgreSQL
    op.create_table(
        "workflows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("definition_json", JSONB, nullable=False),
        sa.Column("is_template", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("template_source_id", UUID(as_uuid=True), sa.ForeignKey("workflows.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_workflows_owner_user_id", "workflows", ["owner_user_id"])

    # workflow_runs table
    op.create_table(
        "workflow_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workflow_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workflows.id"),
            nullable=False,
        ),
        sa.Column("owner_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("trigger_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("checkpoint_id", sa.String(255), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_json", JSONB, nullable=True),
    )
    op.create_index("ix_workflow_runs_workflow_id", "workflow_runs", ["workflow_id"])
    op.create_index("ix_workflow_runs_owner_user_id", "workflow_runs", ["owner_user_id"])

    # workflow_triggers table
    op.create_table(
        "workflow_triggers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workflow_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workflows.id"),
            nullable=False,
        ),
        sa.Column("owner_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("trigger_type", sa.String(20), nullable=False),
        sa.Column("cron_expression", sa.String(100), nullable=True),
        sa.Column("webhook_secret", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )
    op.create_index(
        "ix_workflow_triggers_workflow_id", "workflow_triggers", ["workflow_id"]
    )
    op.create_index(
        "ix_workflow_triggers_owner_user_id", "workflow_triggers", ["owner_user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_triggers_owner_user_id", "workflow_triggers")
    op.drop_index("ix_workflow_triggers_workflow_id", "workflow_triggers")
    op.drop_table("workflow_triggers")

    op.drop_index("ix_workflow_runs_owner_user_id", "workflow_runs")
    op.drop_index("ix_workflow_runs_workflow_id", "workflow_runs")
    op.drop_table("workflow_runs")

    op.drop_index("ix_workflows_owner_user_id", "workflows")
    op.drop_table("workflows")
