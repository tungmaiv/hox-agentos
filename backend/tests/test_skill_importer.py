"""Tests for SkillImporter -- SKILL.md parsing and URL import."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skills.importer import SkillImportError, SkillImporter


@pytest.fixture
def importer() -> SkillImporter:
    return SkillImporter()


_VALID_SKILL_MD = """---
name: email_digest
description: Summarize daily emails into a brief report
version: 1.0.0
slash_command: /digest
---
This skill fetches your emails and creates a summary.

## Usage
Just type /digest in the chat.
"""

_PROCEDURAL_SKILL_MD = """---
name: daily_report
description: Generate daily project report
version: 1.0.0
skill_type: procedural
slash_command: /report
procedure:
  schema_version: "1.0"
  steps:
    - id: fetch
      type: tool
      tool: crm.list_projects
    - id: summarize
      type: llm
      model_alias: blitz/fast
      prompt_template: "Summarize: {{fetch.output}}"
---
Generates a daily report from CRM data.
"""

_MISSING_FRONTMATTER = """No frontmatter here, just plain text."""

_MISSING_REQUIRED_FIELDS = """---
name: incomplete_skill
---
Some instructions.
"""


class TestParseValidSkill:
    def test_valid_instructional_skill(self, importer: SkillImporter) -> None:
        result = importer.parse_skill_md(_VALID_SKILL_MD)
        assert result["name"] == "email_digest"
        assert result["description"] == "Summarize daily emails into a brief report"
        assert result["version"] == "1.0.0"
        assert result["slash_command"] == "/digest"
        assert result["skill_type"] == "instructional"
        assert result["source_type"] == "imported"
        assert "This skill fetches" in result["instruction_markdown"]

    def test_procedural_skill_with_procedure(
        self, importer: SkillImporter
    ) -> None:
        result = importer.parse_skill_md(_PROCEDURAL_SKILL_MD)
        assert result["name"] == "daily_report"
        assert result["skill_type"] == "procedural"
        assert result["procedure_json"] is not None
        assert result["procedure_json"]["schema_version"] == "1.0"
        assert len(result["procedure_json"]["steps"]) == 2

    def test_body_becomes_instruction_markdown(
        self, importer: SkillImporter
    ) -> None:
        result = importer.parse_skill_md(_VALID_SKILL_MD)
        assert "## Usage" in result["instruction_markdown"]

    def test_default_version(self, importer: SkillImporter) -> None:
        md = """---
name: test_skill
description: A test
---
Instructions here.
"""
        result = importer.parse_skill_md(md)
        assert result["version"] == "1.0.0"


class TestParseInvalidSkill:
    def test_missing_frontmatter_raises(self, importer: SkillImporter) -> None:
        with pytest.raises(SkillImportError, match="missing YAML frontmatter"):
            importer.parse_skill_md(_MISSING_FRONTMATTER)

    def test_missing_required_fields_raises(
        self, importer: SkillImporter
    ) -> None:
        with pytest.raises(SkillImportError, match="Missing required"):
            importer.parse_skill_md(_MISSING_REQUIRED_FIELDS)

    def test_invalid_yaml_raises(self, importer: SkillImporter) -> None:
        md = """---
name: test
description: [invalid: yaml: content
---
Body.
"""
        with pytest.raises(SkillImportError, match="Invalid YAML"):
            importer.parse_skill_md(md)

    def test_non_dict_frontmatter_raises(
        self, importer: SkillImporter
    ) -> None:
        md = """---
- just a list
- not a dict
---
Body.
"""
        with pytest.raises(SkillImportError, match="must be a mapping"):
            importer.parse_skill_md(md)


class TestImportFromUrl:
    @pytest.mark.asyncio
    async def test_import_from_url_success(
        self, importer: SkillImporter
    ) -> None:
        """Successful URL import fetches and parses."""
        import httpx

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.text = _VALID_SKILL_MD
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await importer.import_from_url(
                "https://agentskills.io/email_digest"
            )

        assert result["name"] == "email_digest"
        assert result["source_url"] == "https://agentskills.io/email_digest"

    @pytest.mark.asyncio
    async def test_import_from_url_http_error(
        self, importer: SkillImporter
    ) -> None:
        """HTTP error during fetch raises SkillImportError."""
        import httpx

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.side_effect = httpx.HTTPError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(SkillImportError, match="Failed to fetch"):
                await importer.import_from_url("https://bad-url.com/skill")
