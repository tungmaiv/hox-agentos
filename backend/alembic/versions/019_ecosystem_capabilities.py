"""Add ecosystem capabilities foundation: skill_repositories table, mcp_servers.openapi_spec_url,
tool_definitions.config_json, and system.capabilities tool seed.

Revision ID: 019
Revises: 018
Create Date: 2026-03-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None

# JSON type compatible with both SQLite (tests) and PostgreSQL (production)
_JSONB_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    # 1. Create skill_repositories table
    op.create_table(
        "skill_repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cached_index", _JSONB_type, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 2. Add openapi_spec_url to mcp_servers
    op.add_column(
        "mcp_servers",
        sa.Column("openapi_spec_url", sa.Text(), nullable=True),
    )

    # 3. Add config_json to tool_definitions
    op.add_column(
        "tool_definitions",
        sa.Column("config_json", _JSONB_type, nullable=True),
    )

    # 4. Seed system.capabilities tool
    op.execute("""
        INSERT INTO tool_definitions (
            id,
            name,
            display_name,
            description,
            handler_type,
            handler_module,
            handler_function,
            input_schema,
            status,
            is_active,
            sandbox_required
        )
        VALUES (
            gen_random_uuid(),
            'system.capabilities',
            'System Capabilities',
            'List all registered agents, tools, skills, and MCP servers available to the current user',
            'backend',
            'capabilities.tool',
            'system_capabilities',
            '{"type": "object", "properties": {}, "required": [], "required_permissions": ["chat"]}'::jsonb,
            'active',
            true,
            false
        )
        ON CONFLICT (name, version) DO NOTHING
    """)


def downgrade() -> None:
    # Remove system.capabilities seed
    op.execute("DELETE FROM tool_definitions WHERE name = 'system.capabilities'")

    # Remove config_json from tool_definitions
    op.drop_column("tool_definitions", "config_json")

    # Remove openapi_spec_url from mcp_servers
    op.drop_column("mcp_servers", "openapi_spec_url")

    # Drop skill_repositories table
    op.drop_table("skill_repositories")
