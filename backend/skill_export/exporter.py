"""
Skill exporter — builds agentskills.io-compliant zip files from a SkillDefinition.

Zip structure:
    {skill.name}/
    ├── SKILL.md                  # always present
    ├── scripts/
    │   └── procedure.json        # if skill_type == "procedural"
    └── references/
        └── schemas.json          # if input_schema or output_schema defined

SKILL.md format follows the agentskills.io specification:
    - YAML frontmatter between --- delimiters
    - Body contains the instruction_markdown
"""
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any

import yaml

import structlog

logger = structlog.get_logger(__name__)


def build_skill_zip(skill: Any) -> io.BytesIO:
    """
    Build an in-memory zip archive for the given SkillDefinition.

    The archive follows the agentskills.io format:
      - {name}/SKILL.md — YAML frontmatter + instruction body
      - {name}/scripts/procedure.json — present only for procedural skills
      - {name}/references/schemas.json — present only when schemas defined

    Args:
        skill: A SkillDefinition ORM object (or duck-typed equivalent).

    Returns:
        A BytesIO object seeked to position 0, ready for streaming.
    """
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        base_dir = skill.name

        # ── SKILL.md ──────────────────────────────────────────────────────
        skill_md = _build_skill_md(skill)
        zf.writestr(f"{base_dir}/SKILL.md", skill_md)

        # ── scripts/procedure.json ─────────────────────────────────────────
        if skill.procedure_json is not None:
            procedure_bytes = json.dumps(skill.procedure_json, indent=2, ensure_ascii=False)
            zf.writestr(f"{base_dir}/scripts/procedure.json", procedure_bytes)

        # ── references/schemas.json ────────────────────────────────────────
        if skill.input_schema is not None or skill.output_schema is not None:
            schemas = {
                "input_schema": skill.input_schema,
                "output_schema": skill.output_schema,
            }
            schemas_bytes = json.dumps(schemas, indent=2, ensure_ascii=False)
            zf.writestr(f"{base_dir}/references/schemas.json", schemas_bytes)

    buf.seek(0)

    logger.info(
        "skill_exported",
        skill_name=skill.name,
        skill_version=getattr(skill, "version", "unknown"),
        skill_type=skill.skill_type,
    )

    return buf


def _build_skill_md(skill: Any) -> str:
    """
    Build the SKILL.md content with agentskills.io-compliant YAML frontmatter.

    Frontmatter fields:
      - name: skill name
      - description: skill description (max 1024 chars, truncated if necessary)
      - metadata: author, version, skill_type, exported_at, optional slash_command/source_type
    """
    exported_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    metadata: dict[str, Any] = {
        "author": "blitz-agentos",
        "version": skill.version,
        "skill_type": skill.skill_type,
        "exported_at": exported_at,
    }
    if skill.slash_command:
        metadata["slash_command"] = skill.slash_command
    if skill.source_type:
        metadata["source_type"] = skill.source_type

    description = skill.description or ""
    # Truncate description to 1024 chars per agentskills.io spec
    if len(description) > 1024:
        description = description[:1021] + "..."

    frontmatter: dict[str, Any] = {
        "name": skill.name,
        "description": description,
        "metadata": metadata,
    }

    yaml_str = yaml.dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )

    body = skill.instruction_markdown or ""

    return f"---\n{yaml_str}---\n\n{body}"
