"""
SkillImporter -- parses AgentSkills SKILL.md format and imports from URL or ZIP.

The SKILL.md format uses YAML frontmatter (between --- delimiters) followed
by markdown body text that becomes the instruction_markdown.

Required frontmatter fields: name, description
Optional: version, skill_type, slash_command, procedure (for procedural skills),
          license, compatibility, metadata (dict), allowed-tools (space-delimited),
          tags (list), category, source_url

If `procedure` key is present in frontmatter, the skill is treated as
procedural and procedure_json is populated from it.

ZIP bundle import:
  - ZIP must contain SKILL.md at root or in a single top-level directory.
  - MANIFEST.json is optional: if present, its fields are used as fallback
    (SKILL.md frontmatter takes precedence on conflict).
  - assets/ directory is silently ignored.
"""
import io
import json
import re
import zipfile
from typing import Any

import httpx
import structlog
import yaml

logger = structlog.get_logger(__name__)

# Pattern to extract YAML frontmatter
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)", re.DOTALL)

_REQUIRED_FIELDS = {"name", "description"}


class SkillImportError(Exception):
    """Raised when skill import fails."""


def _parse_allowed_tools(raw: Any) -> list[str] | None:
    """Parse allowed-tools field: space-delimited string or list."""
    if raw is None:
        return None
    if isinstance(raw, list):
        return [str(t) for t in raw]
    if isinstance(raw, str):
        parts = raw.split()
        return parts if parts else None
    return None


class SkillImporter:
    """Parses and imports skills from AgentSkills SKILL.md format."""

    def parse_skill_md(self, content: str) -> dict[str, Any]:
        """Parse AgentSkills SKILL.md format.

        Args:
            content: Raw SKILL.md content with YAML frontmatter and
                markdown body.

        Returns:
            Dict ready for SkillDefinitionCreate schema.

        Raises:
            SkillImportError: If content is malformed or missing required fields.
        """
        match = _FRONTMATTER_RE.match(content)
        if not match:
            raise SkillImportError(
                "Invalid SKILL.md format: missing YAML frontmatter "
                "(expected --- delimiters)"
            )

        yaml_text = match.group(1)
        body_text = match.group(2).strip()

        try:
            frontmatter = yaml.safe_load(yaml_text)
        except yaml.YAMLError as exc:
            raise SkillImportError(
                f"SKILL.md frontmatter parse error: {exc}"
            ) from exc

        if not isinstance(frontmatter, dict):
            raise SkillImportError("YAML frontmatter must be a mapping")

        # Validate required fields
        missing = _REQUIRED_FIELDS - set(frontmatter.keys())
        if missing:
            raise SkillImportError(
                f"Missing required frontmatter fields: {', '.join(sorted(missing))}"
            )

        # Build skill data dict
        skill_data: dict[str, Any] = {
            "name": frontmatter["name"],
            "description": frontmatter["description"],
            "version": frontmatter.get("version", "1.0.0"),
            "slash_command": frontmatter.get("slash_command"),
            "source_type": "imported",
        }

        # Handle skill type and procedure
        if "procedure" in frontmatter:
            skill_data["skill_type"] = "procedural"
            skill_data["procedure_json"] = frontmatter["procedure"]
        else:
            skill_data["skill_type"] = frontmatter.get(
                "skill_type", "instructional"
            )

        # Body text becomes instruction_markdown
        if body_text:
            skill_data["instruction_markdown"] = body_text

        # Optional core fields
        if "display_name" in frontmatter:
            skill_data["display_name"] = frontmatter["display_name"]
        if "input_schema" in frontmatter:
            skill_data["input_schema"] = frontmatter["input_schema"]
        if "output_schema" in frontmatter:
            skill_data["output_schema"] = frontmatter["output_schema"]

        # agentskills.io standard fields
        if "license" in frontmatter:
            skill_data["license"] = frontmatter["license"]
        if "compatibility" in frontmatter:
            skill_data["compatibility"] = frontmatter["compatibility"]
        if "metadata" in frontmatter and isinstance(frontmatter["metadata"], dict):
            skill_data["metadata_json"] = frontmatter["metadata"]
        if "allowed-tools" in frontmatter:
            parsed = _parse_allowed_tools(frontmatter["allowed-tools"])
            if parsed is not None:
                skill_data["allowed_tools"] = parsed
        if "tags" in frontmatter:
            raw_tags = frontmatter["tags"]
            skill_data["tags"] = (
                raw_tags if isinstance(raw_tags, list) else [str(raw_tags)]
            )
        if "category" in frontmatter:
            skill_data["category"] = frontmatter["category"]

        logger.info(
            "skill_md_parsed",
            name=skill_data["name"],
            skill_type=skill_data["skill_type"],
        )
        return skill_data

    def import_from_zip(self, zip_bytes: bytes) -> dict[str, Any]:
        """Parse a ZIP bundle containing SKILL.md (and optional MANIFEST.json).

        ZIP structure:
            {skill-name}/SKILL.md   — required
            {skill-name}/MANIFEST.json  — optional metadata fallback
            {skill-name}/assets/    — optional, ignored

        Args:
            zip_bytes: Raw bytes of the ZIP archive.

        Returns:
            Parsed skill data dict.

        Raises:
            SkillImportError: If ZIP is corrupt, missing SKILL.md, or SKILL.md is invalid.
        """
        try:
            zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        except zipfile.BadZipFile as exc:
            raise SkillImportError("Invalid ZIP file") from exc

        with zf:
            names = zf.namelist()

            # Find SKILL.md: accept root-level or inside a single top-level dir
            skill_md_path: str | None = None
            for n in names:
                parts = n.replace("\\", "/").split("/")
                filename = parts[-1]
                if filename == "SKILL.md":
                    skill_md_path = n
                    break

            if skill_md_path is None:
                raise SkillImportError("ZIP must contain SKILL.md")

            try:
                skill_md_content = zf.read(skill_md_path).decode("utf-8")
            except Exception as exc:
                raise SkillImportError(
                    f"Failed to read SKILL.md from ZIP: {exc}"
                ) from exc

            # Parse SKILL.md (primary source)
            skill_data = self.parse_skill_md(skill_md_content)

            # Try MANIFEST.json as fallback for missing fields
            manifest_path: str | None = None
            skill_md_dir = "/".join(skill_md_path.replace("\\", "/").split("/")[:-1])
            for n in names:
                n_dir = "/".join(n.replace("\\", "/").split("/")[:-1])
                if n.endswith("MANIFEST.json") and n_dir == skill_md_dir:
                    manifest_path = n
                    break

            if manifest_path is not None:
                try:
                    manifest_raw = zf.read(manifest_path).decode("utf-8")
                    manifest = json.loads(manifest_raw)
                    if isinstance(manifest, dict):
                        _merge_manifest(skill_data, manifest)
                        logger.info("skill_manifest_merged", path=manifest_path)
                except (json.JSONDecodeError, Exception):
                    # MANIFEST.json is optional — warn but don't reject
                    logger.warning(
                        "skill_manifest_invalid",
                        path=manifest_path,
                    )

        logger.info(
            "skill_imported_from_zip",
            name=skill_data.get("name"),
            skill_type=skill_data.get("skill_type"),
        )
        return skill_data

    async def import_from_url(self, url: str) -> dict[str, Any]:
        """Fetch a SKILL.md or ZIP bundle from a URL and parse it.

        Args:
            url: URL to fetch the SKILL.md content from.

        Returns:
            Parsed skill data dict.

        Raises:
            SkillImportError: If fetch fails or content is invalid.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SkillImportError(
                f"Failed to fetch skill from {url}: {exc}"
            ) from exc

        content_type = response.headers.get("content-type", "")
        is_zip = (
            url.lower().endswith(".zip")
            or "zip" in content_type
            or "octet-stream" in content_type
        )

        if is_zip:
            skill_data = self.import_from_zip(response.content)
        else:
            skill_data = self.parse_skill_md(response.text)

        skill_data["source_url"] = url

        logger.info(
            "skill_imported_from_url",
            url=url,
            name=skill_data["name"],
        )
        return skill_data


def _merge_manifest(skill_data: dict[str, Any], manifest: dict[str, Any]) -> None:
    """Merge MANIFEST.json fields into skill_data (SKILL.md takes precedence)."""
    field_map = {
        "license": "license",
        "compatibility": "compatibility",
        "metadata": "metadata_json",
        "allowed_tools": "allowed_tools",
        "tags": "tags",
        "category": "category",
        "source_url": "source_url",
    }
    for manifest_key, skill_key in field_map.items():
        if manifest_key in manifest and skill_key not in skill_data:
            value = manifest[manifest_key]
            if value is not None:
                skill_data[skill_key] = value
