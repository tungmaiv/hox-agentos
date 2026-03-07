"""
Skill exporter — builds agentskills.io-compliant zip files from a SkillDefinition.

Zip structure:
    {skill.name}/
    ├── SKILL.md                  # always present
    ├── MANIFEST.json             # full metadata mirror (always present)
    ├── scripts/
    │   └── procedure.json        # if skill_type == "procedural"
    ├── references/
    │   └── schemas.json          # if input_schema or output_schema defined
    └── assets/                   # empty placeholder directory

SKILL.md format follows the agentskills.io specification:
    - YAML frontmatter between --- delimiters
    - Body contains the instruction_markdown
"""
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any

import structlog
import yaml

from core.models.skill_definition import SkillDefinition

logger = structlog.get_logger(__name__)


def build_skill_zip(skill: SkillDefinition) -> io.BytesIO:
    """
    Build an in-memory zip archive for the given SkillDefinition.

    The archive follows the agentskills.io format:
      - {name}/SKILL.md — YAML frontmatter + instruction body
      - {name}/MANIFEST.json — full metadata mirror
      - {name}/scripts/procedure.json — present only for procedural skills
      - {name}/references/schemas.json — present only when schemas defined
      - {name}/assets/ — empty placeholder directory

    Args:
        skill: A SkillDefinition ORM object (or duck-typed equivalent).

    Returns:
        A BytesIO object seeked to position 0, ready for streaming.
    """
    buf = io.BytesIO()
    exported_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        base_dir = skill.name

        # ── SKILL.md ──────────────────────────────────────────────────────
        skill_md = _build_skill_md(skill, exported_at)
        zf.writestr(f"{base_dir}/SKILL.md", skill_md)

        # ── MANIFEST.json ─────────────────────────────────────────────────
        manifest = _build_manifest(skill, exported_at)
        manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False)
        zf.writestr(f"{base_dir}/MANIFEST.json", manifest_bytes)

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

        # ── assets/ empty placeholder ─────────────────────────────────────
        zf.writestr(f"{base_dir}/assets/.gitkeep", "")

    buf.seek(0)

    logger.info(
        "skill_exported",
        skill_name=skill.name,
        skill_version=getattr(skill, "version", "unknown"),
        skill_type=skill.skill_type,
    )

    return buf


def _build_manifest(skill: SkillDefinition, exported_at: str) -> dict[str, Any]:
    """Build the MANIFEST.json full metadata mirror."""
    return {
        "schema_version": "1.0",
        "name": skill.name,
        "description": skill.description,
        "version": skill.version,
        "license": getattr(skill, "license", None),
        "compatibility": getattr(skill, "compatibility", None),
        "metadata": getattr(skill, "metadata_json", None),
        "allowed_tools": getattr(skill, "allowed_tools", None),
        "tags": getattr(skill, "tags", None),
        "category": getattr(skill, "category", None),
        "source_url": getattr(skill, "source_url", None),
        "skill_type": skill.skill_type,
        "slash_command": skill.slash_command,
        "source_type": skill.source_type,
        "security_score": getattr(skill, "security_score", None),
        "exported_at": exported_at,
        "procedure": skill.procedure_json,
    }


def _build_skill_md(skill: SkillDefinition, exported_at: str) -> str:
    """
    Build the SKILL.md content with agentskills.io-compliant YAML frontmatter.

    Frontmatter fields:
      - name, description: core identity
      - license, compatibility: standard fields
      - allowed-tools: space-delimited string (per agentskills.io spec)
      - tags: list
      - category: string
      - metadata: dict (author, version, skill_type, exported_at, slash_command, source_type)
    """
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
    }

    # Add new standard fields (only if non-null)
    license_val = getattr(skill, "license", None)
    if license_val:
        frontmatter["license"] = license_val

    compatibility_val = getattr(skill, "compatibility", None)
    if compatibility_val:
        frontmatter["compatibility"] = compatibility_val

    allowed_tools_val = getattr(skill, "allowed_tools", None)
    if allowed_tools_val:
        # Per spec: space-delimited string in SKILL.md frontmatter
        frontmatter["allowed-tools"] = " ".join(allowed_tools_val)

    tags_val = getattr(skill, "tags", None)
    if tags_val:
        frontmatter["tags"] = tags_val

    category_val = getattr(skill, "category", None)
    if category_val:
        frontmatter["category"] = category_val

    frontmatter["metadata"] = metadata

    yaml_str = yaml.dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )

    body = skill.instruction_markdown or ""

    return f"---\n{yaml_str}---\n\n{body}"
