"""030_mcp_catalog

Revision ID: 617b296e937a
Revises: c12d84fc28f9
Create Date: 2026-03-12 09:55:19.615168

Creates the mcp_server_catalog table and seeds 3 pre-built MCP server entries:
  - context7: npm @upstash/context7-mcp (library documentation)
  - mcp-server-fetch: pip mcp-server-fetch (web page fetch)
  - mcp-server-filesystem: npm @modelcontextprotocol/server-filesystem (filesystem)

Catalog = pre-built server definitions not yet installed.
Installation creates a registry_entries row.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '617b296e937a'
down_revision: Union[str, None] = 'c12d84fc28f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Create mcp_server_catalog table ---
    op.create_table(
        "mcp_server_catalog",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("package_manager", sa.String(10), nullable=False),
        sa.Column("package_name", sa.String(200), nullable=False),
        sa.Column("command", sa.String(200), nullable=False),
        sa.Column(
            "args",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "env_vars",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("name", name="uq_mcp_server_catalog_name"),
    )

    # --- Seed 3 pre-built MCP server entries ---
    op.execute(
        sa.text(
            """
            INSERT INTO mcp_server_catalog
                (id, name, display_name, description, package_manager, package_name, command, args, env_vars)
            VALUES
                (
                    gen_random_uuid(),
                    'context7',
                    'Context7',
                    'Library documentation lookup via Context7',
                    'npm',
                    '@upstash/context7-mcp',
                    'npx',
                    '["-y", "@upstash/context7-mcp@latest"]',
                    '{"UPSTASH_REDIS_REST_URL": "Required", "UPSTASH_REDIS_REST_TOKEN": "Required"}'
                ),
                (
                    gen_random_uuid(),
                    'mcp-server-fetch',
                    'MCP Fetch',
                    'Web page fetch and content extraction',
                    'pip',
                    'mcp-server-fetch',
                    'python',
                    '["-m", "mcp_server_fetch"]',
                    '{}'
                ),
                (
                    gen_random_uuid(),
                    'mcp-server-filesystem',
                    'MCP Filesystem',
                    'Local filesystem read/write access',
                    'npm',
                    '@modelcontextprotocol/server-filesystem',
                    'npx',
                    '["-y", "@modelcontextprotocol/server-filesystem"]',
                    '{}'
                )
            """
        )
    )


def downgrade() -> None:
    op.drop_table("mcp_server_catalog")
