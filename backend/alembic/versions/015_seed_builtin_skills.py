"""Seed 3 built-in skill_definitions rows (summarize, debug, export).

Seeds instructional skills with slash commands into skill_definitions.
Uses ON CONFLICT DO NOTHING for idempotency.

Revision ID: 015
Revises: 014
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Seed 3 built-in instructional skills with slash commands.
    # ON CONFLICT (name, version) DO NOTHING ensures idempotency on re-run.

    op.execute(
        sa.text(
            "INSERT INTO skill_definitions "
            "(id, name, display_name, description, version, is_active, status, "
            "skill_type, slash_command, source_type, instruction_markdown, security_score) "
            "VALUES (gen_random_uuid(), :name, :display_name, :description, '1.0.0', true, "
            "'active', :skill_type, :slash_command, 'builtin', :instruction_markdown, 90) "
            "ON CONFLICT (name, version) DO NOTHING"
        ).bindparams(
            name="summarize",
            display_name="Summarize",
            description="Summarize a conversation, document, or block of text into key points.",
            skill_type="instructional",
            slash_command="/summarize",
            instruction_markdown=(
                "You are a summarization assistant. When the user invokes /summarize, produce a\n"
                "concise bullet-point summary of the content they provide (or of the recent\n"
                "conversation if no content is given). Keep each bullet under 20 words."
            ),
        )
    )

    op.execute(
        sa.text(
            "INSERT INTO skill_definitions "
            "(id, name, display_name, description, version, is_active, status, "
            "skill_type, slash_command, source_type, instruction_markdown, security_score) "
            "VALUES (gen_random_uuid(), :name, :display_name, :description, '1.0.0', true, "
            "'active', :skill_type, :slash_command, 'builtin', :instruction_markdown, 90) "
            "ON CONFLICT (name, version) DO NOTHING"
        ).bindparams(
            name="debug",
            display_name="Debug",
            description="Analyze and diagnose a problem or error with step-by-step reasoning.",
            skill_type="instructional",
            slash_command="/debug",
            instruction_markdown=(
                "You are a debugging assistant. When the user invokes /debug, systematically\n"
                "analyze the error or problem they describe. Follow this structure:\n"
                "1. Identify the root cause.\n"
                "2. List 2-3 possible fixes.\n"
                "3. Recommend the best fix with a brief rationale."
            ),
        )
    )

    op.execute(
        sa.text(
            "INSERT INTO skill_definitions "
            "(id, name, display_name, description, version, is_active, status, "
            "skill_type, slash_command, source_type, instruction_markdown, security_score) "
            "VALUES (gen_random_uuid(), :name, :display_name, :description, '1.0.0', true, "
            "'active', :skill_type, :slash_command, 'builtin', :instruction_markdown, 90) "
            "ON CONFLICT (name, version) DO NOTHING"
        ).bindparams(
            name="export",
            display_name="Export",
            description="Format the current conversation or data as a structured export (Markdown or JSON).",
            skill_type="instructional",
            slash_command="/export",
            instruction_markdown=(
                "You are a data formatting assistant. When the user invokes /export, take the\n"
                "most recent conversation content and format it as clean Markdown suitable for\n"
                "copy-pasting into a document. If the user specifies JSON, output valid JSON instead."
            ),
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM skill_definitions WHERE name IN ('summarize', 'debug', 'export') "
            "AND source_type = 'builtin'"
        )
    )
