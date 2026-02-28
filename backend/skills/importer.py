"""
SkillImporter -- parses AgentSkills SKILL.md format and imports from URL.

The SKILL.md format uses YAML frontmatter (between --- delimiters) followed
by markdown body text that becomes the instruction_markdown.

Required frontmatter fields: name, description
Optional: version, skill_type, slash_command, procedure (for procedural skills)

If `procedure` key is present in frontmatter, the skill is treated as
procedural and procedure_json is populated from it.
"""
import re
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
            raise SkillImportError(f"Invalid YAML frontmatter: {exc}") from exc

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

        # Optional fields
        if "display_name" in frontmatter:
            skill_data["display_name"] = frontmatter["display_name"]
        if "input_schema" in frontmatter:
            skill_data["input_schema"] = frontmatter["input_schema"]
        if "output_schema" in frontmatter:
            skill_data["output_schema"] = frontmatter["output_schema"]

        logger.info(
            "skill_md_parsed",
            name=skill_data["name"],
            skill_type=skill_data["skill_type"],
        )
        return skill_data

    async def import_from_url(self, url: str) -> dict[str, Any]:
        """Fetch a SKILL.md from a URL and parse it.

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

        content = response.text
        skill_data = self.parse_skill_md(content)
        skill_data["source_url"] = url

        logger.info(
            "skill_imported_from_url",
            url=url,
            name=skill_data["name"],
        )
        return skill_data
