"""Create extensibility registry tables, evolve mcp_servers, seed data.

Creates 6 new tables (agent_definitions, tool_definitions, skill_definitions,
artifact_permissions, user_artifact_permissions, role_permissions), adds 4 columns
to mcp_servers, seeds role_permissions from ROLE_PERMISSIONS dict, seeds
agent_definitions with 4 built-in agents, and migrates tool_acl rows into
artifact_permissions.

Revision ID: 014
Revises: 013
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── agent_definitions ────────────────────────────────────────────────
    op.create_table(
        "agent_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(32), nullable=False, server_default="1.0.0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handler_module", sa.Text(), nullable=True),
        sa.Column("handler_function", sa.Text(), nullable=True),
        sa.Column(
            "routing_keywords",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "config_json",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", name="uq_agent_name_version"),
    )

    # ── tool_definitions ─────────────────────────────────────────────────
    op.create_table(
        "tool_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(32), nullable=False, server_default="1.0.0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handler_type", sa.String(20), nullable=False, server_default="backend"),
        sa.Column("handler_module", sa.Text(), nullable=True),
        sa.Column("handler_function", sa.Text(), nullable=True),
        sa.Column("mcp_server_id", sa.UUID(), nullable=True),
        sa.Column("mcp_tool_name", sa.Text(), nullable=True),
        sa.Column("sandbox_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "input_schema",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "output_schema",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", name="uq_tool_name_version"),
    )

    # ── skill_definitions ────────────────────────────────────────────────
    op.create_table(
        "skill_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(32), nullable=False, server_default="1.0.0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skill_type", sa.String(20), nullable=False),
        sa.Column("slash_command", sa.String(64), nullable=True, unique=True),
        sa.Column("source_type", sa.String(20), nullable=False, server_default="builtin"),
        sa.Column("instruction_markdown", sa.Text(), nullable=True),
        sa.Column(
            "procedure_json",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "input_schema",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "output_schema",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("security_score", sa.Integer(), nullable=True),
        sa.Column(
            "security_report",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", name="uq_skill_name_version"),
    )

    # ── artifact_permissions ─────────────────────────────────────────────
    op.create_table(
        "artifact_permissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("artifact_type", sa.String(20), nullable=False),
        sa.Column("artifact_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "artifact_type", "artifact_id", "role",
            name="uq_artifact_perm_type_id_role",
        ),
    )
    op.create_index(
        "ix_artifact_perm_type_id",
        "artifact_permissions",
        ["artifact_type", "artifact_id"],
    )

    # ── user_artifact_permissions ────────────────────────────────────────
    op.create_table(
        "user_artifact_permissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("artifact_type", sa.String(20), nullable=False),
        sa.Column("artifact_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "artifact_type", "artifact_id", "user_id",
            name="uq_user_artifact_perm_type_id_user",
        ),
    )
    op.create_index(
        "ix_user_artifact_perm_type_id",
        "user_artifact_permissions",
        ["artifact_type", "artifact_id"],
    )

    # ── role_permissions ─────────────────────────────────────────────────
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("permission", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role", "permission", name="uq_role_permission"),
    )
    op.create_index("ix_role_permissions_role", "role_permissions", ["role"])

    # ── Evolve mcp_servers with 4 new columns ────────────────────────────
    op.add_column("mcp_servers", sa.Column("version", sa.Text(), nullable=True))
    op.add_column("mcp_servers", sa.Column("display_name", sa.Text(), nullable=True))
    op.add_column(
        "mcp_servers",
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
    )
    op.add_column(
        "mcp_servers",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Migrate mcp_servers.is_active → status
    op.execute(
        "UPDATE mcp_servers SET status = 'active' WHERE is_active = true"
    )
    op.execute(
        "UPDATE mcp_servers SET status = 'disabled' WHERE is_active = false"
    )

    # ── Seed role_permissions from ROLE_PERMISSIONS dict ──────────────────
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("id", sa.UUID),
        sa.column("role", sa.String),
        sa.column("permission", sa.String),
    )

    # Exact values from security/rbac.py ROLE_PERMISSIONS
    role_perms = {
        "employee": [
            "chat", "tool:email", "tool:calendar", "tool:project", "crm:read",
        ],
        "manager": [
            "chat", "tool:email", "tool:calendar", "tool:project", "crm:read",
            "crm:write", "tool:reports", "workflow:create",
        ],
        "team-lead": [
            "chat", "tool:email", "tool:calendar", "tool:project", "crm:read",
            "crm:write", "tool:reports", "workflow:create", "workflow:approve",
        ],
        "it-admin": [
            "chat", "tool:email", "tool:calendar", "tool:project", "crm:read",
            "crm:write", "tool:reports", "workflow:create", "workflow:approve",
            "tool:admin", "sandbox:execute", "registry:manage",
        ],
        "executive": [
            "chat", "tool:reports",
        ],
    }

    # Use raw SQL for UUID generation since op.bulk_insert doesn't support sa.text() in values
    for role, perms in role_perms.items():
        for perm in perms:
            op.execute(
                sa.text(
                    "INSERT INTO role_permissions (id, role, permission) "
                    "VALUES (gen_random_uuid(), :role, :perm)"
                ).bindparams(role=role, perm=perm)
            )

    # ── Seed agent_definitions with 4 built-in agents ────────────────────
    agents = [
        {
            "name": "master_agent",
            "display_name": "Master Agent",
            "description": "Main conversational agent with sub-agent routing",
            "handler_module": "agents.master_agent",
            "handler_function": "create_master_graph",
            "routing_keywords": "[]",
        },
        {
            "name": "email_agent",
            "display_name": "Email Agent",
            "description": "Handles email-related tasks",
            "handler_module": "agents.subagents.email_agent",
            "handler_function": "_email_agent_node",
            "routing_keywords": '["email", "mail", "inbox", "send"]',
        },
        {
            "name": "calendar_agent",
            "display_name": "Calendar Agent",
            "description": "Handles calendar and scheduling tasks",
            "handler_module": "agents.subagents.calendar_agent",
            "handler_function": "_calendar_agent_node",
            "routing_keywords": '["calendar", "meeting", "schedule", "appointment"]',
        },
        {
            "name": "project_agent",
            "display_name": "Project Agent",
            "description": "Handles project management tasks",
            "handler_module": "agents.subagents.project_agent",
            "handler_function": "_project_agent_node",
            "routing_keywords": '["project", "task", "kanban", "sprint"]',
        },
    ]

    for agent in agents:
        op.execute(
            sa.text(
                "INSERT INTO agent_definitions "
                "(id, name, display_name, description, handler_module, handler_function, routing_keywords) "
                "VALUES (gen_random_uuid(), :name, :display_name, :description, "
                ":handler_module, :handler_function, CAST(:routing_keywords AS jsonb))"
            ).bindparams(**agent)
        )

    # ── Data migration: tool_acl → artifact_permissions ──────────────────
    # Migrate existing tool_acl rows as tool-type artifact permissions.
    # tool_acl has (user_id, tool_name, allowed) -- we map to
    # artifact_permissions (artifact_type='tool', artifact_id=tool_id, role, allowed)
    # NOTE: tool_acl stores user_id not role, so we migrate user-level entries
    # into user_artifact_permissions instead of artifact_permissions.
    op.execute(
        sa.text(
            "INSERT INTO user_artifact_permissions "
            "(id, artifact_type, artifact_id, user_id, allowed, status) "
            "SELECT gen_random_uuid(), 'tool', id, user_id, allowed, 'active' "
            "FROM tool_acl"
        )
    )


def downgrade() -> None:
    # Remove migrated data
    op.execute("DELETE FROM user_artifact_permissions WHERE artifact_type = 'tool'")

    # Drop new columns from mcp_servers
    op.drop_column("mcp_servers", "last_seen_at")
    op.drop_column("mcp_servers", "status")
    op.drop_column("mcp_servers", "display_name")
    op.drop_column("mcp_servers", "version")

    # Drop tables in reverse order
    op.drop_index("ix_role_permissions_role", table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_index("ix_user_artifact_perm_type_id", table_name="user_artifact_permissions")
    op.drop_table("user_artifact_permissions")
    op.drop_index("ix_artifact_perm_type_id", table_name="artifact_permissions")
    op.drop_table("artifact_permissions")
    op.drop_table("skill_definitions")
    op.drop_table("tool_definitions")
    op.drop_table("agent_definitions")
