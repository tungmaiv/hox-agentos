"""Create registry_entries table; migrate agent_definitions, skill_definitions,
tool_definitions, mcp_servers into unified registry; drop old tables.

Revision ID: c12d84fc28f9
Revises: 027
Create Date: 2026-03-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c12d84fc28f9"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Sentinel owner UUID used when original table has no owner column
_SYSTEM_OWNER = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    # ── Create unified registry_entries table ────────────────────────────
    op.create_table(
        "registry_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "config",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("owner_id", sa.UUID(), nullable=False),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type", "name", name="uq_registry_type_name"),
    )

    # ── Migrate agent_definitions → registry_entries ────────────────────
    # agent_definitions has no owner column; use system owner sentinel.
    # name+version may have duplicates (e.g. same agent multiple versions) so
    # we embed version in name when != 1.0.0 to preserve uniqueness.
    op.execute(
        sa.text(
            """
            INSERT INTO registry_entries
                (id, type, name, display_name, description, config, status, owner_id,
                 created_at, updated_at)
            SELECT
                id,
                'agent',
                name || CASE WHEN version != '1.0.0' THEN ':' || version ELSE '' END,
                display_name,
                description,
                COALESCE(
                    jsonb_strip_nulls(jsonb_build_object(
                        'version', version,
                        'is_active', is_active,
                        'handler_module', handler_module,
                        'handler_function', handler_function,
                        'routing_keywords', routing_keywords,
                        'config_json', config_json
                    )),
                    '{}'::jsonb
                ),
                CASE
                    WHEN status IN ('active', 'draft', 'archived') THEN status
                    WHEN is_active THEN 'active'
                    ELSE 'archived'
                END,
                '00000000-0000-0000-0000-000000000001'::uuid,
                created_at,
                updated_at
            FROM agent_definitions
            ON CONFLICT (type, name) DO NOTHING
            """
    )
    )

    # ── Migrate skill_definitions → registry_entries ─────────────────────
    # skills have created_by as owner; use COALESCE with system owner
    op.execute(
        sa.text(
            """
            INSERT INTO registry_entries
                (id, type, name, display_name, description, config, status, owner_id,
                 created_at, updated_at)
            SELECT
                id,
                'skill',
                name,
                display_name,
                description,
                jsonb_strip_nulls(jsonb_build_object(
                    'skill_type', skill_type,
                    'version', version,
                    'slash_command', slash_command,
                    'source_type', source_type,
                    'instruction_markdown', instruction_markdown,
                    'procedure_json', procedure_json,
                    'input_schema', input_schema,
                    'output_schema', output_schema,
                    'allowed_tools', allowed_tools,
                    'tags', tags,
                    'category', category,
                    'source_url', source_url,
                    'source_hash', source_hash,
                    'license', license,
                    'compatibility', compatibility,
                    'metadata_json', metadata_json,
                    'is_promoted', is_promoted,
                    'usage_count', usage_count,
                    'security_score', security_score,
                    'security_report', security_report
                )),
                CASE
                    WHEN status IN ('active', 'draft', 'archived') THEN status
                    WHEN status = 'pending_review' THEN 'draft'
                    WHEN is_active THEN 'active'
                    ELSE 'archived'
                END,
                COALESCE(created_by, '00000000-0000-0000-0000-000000000001'::uuid),
                created_at,
                updated_at
            FROM skill_definitions
            ON CONFLICT (type, name) DO NOTHING
            """
    )
    )

    # ── Migrate tool_definitions → registry_entries ───────────────────────
    # tools have no owner column; use system owner sentinel
    op.execute(
        sa.text(
            """
            INSERT INTO registry_entries
                (id, type, name, display_name, description, config, status, owner_id,
                 created_at, updated_at)
            SELECT
                id,
                'tool',
                name,
                display_name,
                description,
                jsonb_strip_nulls(jsonb_build_object(
                    'version', version,
                    'is_active', is_active,
                    'handler_type', handler_type,
                    'handler_module', handler_module,
                    'handler_function', handler_function,
                    'mcp_server_id', mcp_server_id::text,
                    'mcp_tool_name', mcp_tool_name,
                    'sandbox_required', sandbox_required,
                    'handler_code', handler_code,
                    'input_schema', input_schema,
                    'output_schema', output_schema,
                    'config_json', config_json
                )),
                CASE
                    WHEN status IN ('active', 'draft', 'archived') THEN status
                    WHEN is_active THEN 'active'
                    ELSE 'archived'
                END,
                '00000000-0000-0000-0000-000000000001'::uuid,
                created_at,
                updated_at
            FROM tool_definitions
            ON CONFLICT (type, name) DO NOTHING
            """
    )
    )

    # ── Migrate mcp_servers → registry_entries ────────────────────────────
    # auth_token is bytes (LargeBinary) — stored as hex string in config JSONB
    op.execute(
        sa.text(
            """
            INSERT INTO registry_entries
                (id, type, name, display_name, description, config, status, owner_id,
                 created_at, updated_at)
            SELECT
                id,
                'mcp_server',
                name,
                COALESCE(display_name, name),
                NULL,
                jsonb_strip_nulls(jsonb_build_object(
                    'url', url,
                    'version', version,
                    'openapi_spec_url', openapi_spec_url,
                    'is_active', is_active,
                    'auth_token_hex',
                        CASE WHEN auth_token IS NOT NULL
                             THEN encode(auth_token, 'hex')
                             ELSE NULL
                        END
                )),
                CASE
                    WHEN status IN ('active', 'draft', 'archived') THEN status
                    WHEN is_active THEN 'active'
                    ELSE 'archived'
                END,
                '00000000-0000-0000-0000-000000000001'::uuid,
                created_at,
                created_at
            FROM mcp_servers
            ON CONFLICT (type, name) DO NOTHING
            """
    )
    )

    # ── Drop old tables ───────────────────────────────────────────────────
    # Note: skill_repo_index references skill_definitions by name (no FK),
    # so it is safe to drop skill_definitions without cascade.
    op.drop_table("mcp_servers")
    op.drop_table("tool_definitions")
    op.drop_table("skill_definitions")
    op.drop_table("agent_definitions")


def downgrade() -> None:
    # ── Recreate agent_definitions ────────────────────────────────────────
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

    # ── Recreate skill_definitions ────────────────────────────────────────
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
        sa.Column("slash_command", sa.String(64), nullable=True),
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
        sa.Column(
            "allowed_tools",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "tags",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_hash", sa.Text(), nullable=True),
        sa.Column("license", sa.Text(), nullable=True),
        sa.Column("compatibility", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("is_promoted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
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

    # ── Recreate tool_definitions ─────────────────────────────────────────
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
        sa.Column("handler_code", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("name", "version", name="uq_tool_name_version"),
    )

    # ── Recreate mcp_servers ──────────────────────────────────────────────
    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("auth_token", sa.LargeBinary(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("version", sa.Text(), nullable=True),
        sa.Column("openapi_spec_url", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_mcp_server_name"),
    )

    # ── Reverse-migrate from registry_entries ─────────────────────────────

    # Agents: reverse name encoding (name:version back to separate columns)
    op.execute(
        sa.text(
            """
            INSERT INTO agent_definitions
                (id, name, display_name, description, version, is_active, status,
                 handler_module, handler_function, routing_keywords, config_json,
                 created_at, updated_at)
            SELECT
                id,
                CASE WHEN name LIKE '%:%' THEN split_part(name, ':', 1) ELSE name END,
                display_name,
                description,
                COALESCE(config->>'version', '1.0.0'),
                COALESCE((config->>'is_active')::boolean, true),
                CASE WHEN status = 'archived' THEN 'active' ELSE status END,
                config->>'handler_module',
                config->>'handler_function',
                config->'routing_keywords',
                config->'config_json',
                created_at,
                updated_at
            FROM registry_entries
            WHERE type = 'agent' AND deleted_at IS NULL
            """
        )
    )

    # Skills
    op.execute(
        sa.text(
            """
            INSERT INTO skill_definitions
                (id, name, display_name, description, version, is_active, status,
                 skill_type, slash_command, source_type, instruction_markdown,
                 procedure_json, input_schema, output_schema, allowed_tools,
                 tags, category, source_url, source_hash, license, compatibility,
                 metadata_json, is_promoted, usage_count, security_score,
                 security_report, created_by, created_at, updated_at)
            SELECT
                id,
                name,
                display_name,
                description,
                COALESCE(config->>'version', '1.0.0'),
                CASE WHEN status = 'active' THEN true ELSE false END,
                status,
                COALESCE(config->>'skill_type', 'instructional'),
                config->>'slash_command',
                COALESCE(config->>'source_type', 'builtin'),
                config->>'instruction_markdown',
                config->'procedure_json',
                config->'input_schema',
                config->'output_schema',
                config->'allowed_tools',
                config->'tags',
                config->>'category',
                config->>'source_url',
                config->>'source_hash',
                config->>'license',
                config->>'compatibility',
                config->'metadata_json',
                COALESCE((config->>'is_promoted')::boolean, false),
                COALESCE((config->>'usage_count')::integer, 0),
                (config->>'security_score')::integer,
                config->'security_report',
                owner_id,
                created_at,
                updated_at
            FROM registry_entries
            WHERE type = 'skill' AND deleted_at IS NULL
            """
        )
    )

    # Tools
    op.execute(
        sa.text(
            """
            INSERT INTO tool_definitions
                (id, name, display_name, description, version, is_active, status,
                 handler_type, handler_module, handler_function, mcp_server_id,
                 mcp_tool_name, sandbox_required, handler_code,
                 input_schema, output_schema, config_json, created_at, updated_at)
            SELECT
                id,
                name,
                display_name,
                description,
                COALESCE(config->>'version', '1.0.0'),
                CASE WHEN status = 'active' THEN true ELSE false END,
                CASE WHEN status IN ('active', 'draft', 'archived') THEN status ELSE 'active' END,
                COALESCE(config->>'handler_type', 'backend'),
                config->>'handler_module',
                config->>'handler_function',
                CASE WHEN config->>'mcp_server_id' IS NOT NULL AND config->>'mcp_server_id' != 'null'
                     THEN (config->>'mcp_server_id')::uuid
                     ELSE NULL END,
                config->>'mcp_tool_name',
                COALESCE((config->>'sandbox_required')::boolean, false),
                config->>'handler_code',
                config->'input_schema',
                config->'output_schema',
                config->'config_json',
                created_at,
                updated_at
            FROM registry_entries
            WHERE type = 'tool' AND deleted_at IS NULL
            """
        )
    )

    # MCP servers — decode auth_token_hex back to bytes
    op.execute(
        sa.text(
            """
            INSERT INTO mcp_servers
                (id, name, url, auth_token, is_active, version,
                 openapi_spec_url, display_name, status, created_at)
            SELECT
                id,
                name,
                config->>'url',
                CASE WHEN config->>'auth_token_hex' IS NOT NULL
                     THEN decode(config->>'auth_token_hex', 'hex')
                     ELSE NULL
                END,
                COALESCE((config->>'is_active')::boolean, true),
                config->>'version',
                config->>'openapi_spec_url',
                display_name,
                CASE WHEN status IN ('active', 'draft', 'archived') THEN status ELSE 'active' END,
                created_at
            FROM registry_entries
            WHERE type = 'mcp_server' AND deleted_at IS NULL
            """
        )
    )

    # ── Drop registry_entries ─────────────────────────────────────────────
    op.drop_table("registry_entries")
