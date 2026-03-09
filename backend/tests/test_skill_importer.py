"""Tests for SkillImporter -- SKILL.md parsing, URL import, and ZIP bundle import."""
import io
import json
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skills.importer import SkillImportError, SkillImporter
from skills.security_scanner import SecurityScanner


def _make_zip(files: dict[str, str]) -> bytes:
    """Build an in-memory ZIP archive from a dict of {path: content}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()


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
        with pytest.raises(SkillImportError, match="frontmatter parse error"):
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
        mock_response.content = _VALID_SKILL_MD.encode()
        mock_response.headers = {"content-type": "text/plain"}
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


_EXTENDED_SKILL_MD = """---
name: morning-digest
description: Morning productivity digest
version: 2.0.0
license: Apache-2.0
compatibility: Requires email and calendar tools
allowed-tools: "email.fetch calendar.list"
tags:
  - productivity
  - morning
category: communication
metadata:
  author: test-user
  custom_field: value
---
Run your morning digest.
"""

_MANIFEST_JSON = {
    "schema_version": "1.0",
    "name": "morning-digest",
    "description": "Morning productivity digest",
    "license": "MIT",  # should be overridden by SKILL.md's Apache-2.0
    "category": "automation",  # should be overridden by SKILL.md's "communication"
    "tags": ["automation"],  # should be overridden by SKILL.md's tags
    "source_url": "https://example.com/morning-digest",  # fallback — SKILL.md has no source_url
}


class TestExtendedFrontmatterParsing:
    """Tests for parsing of 7 new agentskills.io standard fields."""

    def test_license_parsed(self, importer: SkillImporter) -> None:
        result = importer.parse_skill_md(_EXTENDED_SKILL_MD)
        assert result["license"] == "Apache-2.0"

    def test_compatibility_parsed(self, importer: SkillImporter) -> None:
        result = importer.parse_skill_md(_EXTENDED_SKILL_MD)
        assert result["compatibility"] == "Requires email and calendar tools"

    def test_allowed_tools_space_delimited(self, importer: SkillImporter) -> None:
        result = importer.parse_skill_md(_EXTENDED_SKILL_MD)
        assert result["allowed_tools"] == ["email.fetch", "calendar.list"]

    def test_tags_list(self, importer: SkillImporter) -> None:
        result = importer.parse_skill_md(_EXTENDED_SKILL_MD)
        assert result["tags"] == ["productivity", "morning"]

    def test_category_parsed(self, importer: SkillImporter) -> None:
        result = importer.parse_skill_md(_EXTENDED_SKILL_MD)
        assert result["category"] == "communication"

    def test_metadata_dict(self, importer: SkillImporter) -> None:
        result = importer.parse_skill_md(_EXTENDED_SKILL_MD)
        assert result["metadata_json"] == {"author": "test-user", "custom_field": "value"}

    def test_source_url_parsed_from_frontmatter(self, importer: SkillImporter) -> None:
        md = """---
name: test-skill
description: A test skill.
skill_type: instructional
source_url: https://github.com/example/test-skill
---
Instructions here.
"""
        result = importer.parse_skill_md(md)
        assert result["source_url"] == "https://github.com/example/test-skill"

    def test_missing_standard_fields_are_absent(self, importer: SkillImporter) -> None:
        """Fields not in frontmatter should not appear in skill_data."""
        result = importer.parse_skill_md(_VALID_SKILL_MD)
        assert "license" not in result
        assert "compatibility" not in result
        assert "tags" not in result


class TestZipImport:
    """Tests for import_from_zip()."""

    def test_valid_zip_with_root_skill_md(self, importer: SkillImporter) -> None:
        zip_bytes = _make_zip({"SKILL.md": _VALID_SKILL_MD})
        result = importer.import_from_zip(zip_bytes)
        assert result["name"] == "email_digest"
        assert result["skill_type"] == "instructional"

    def test_valid_zip_with_subdirectory_skill_md(self, importer: SkillImporter) -> None:
        zip_bytes = _make_zip({"email-digest/SKILL.md": _VALID_SKILL_MD})
        result = importer.import_from_zip(zip_bytes)
        assert result["name"] == "email_digest"

    def test_corrupt_zip_raises(self, importer: SkillImporter) -> None:
        with pytest.raises(SkillImportError, match="Invalid ZIP"):
            importer.import_from_zip(b"this is not a zip file")

    def test_zip_without_skill_md_raises(self, importer: SkillImporter) -> None:
        zip_bytes = _make_zip({"README.md": "# Hello"})
        with pytest.raises(SkillImportError, match="ZIP must contain SKILL.md"):
            importer.import_from_zip(zip_bytes)

    def test_zip_with_manifest_merges_fallback_fields(
        self, importer: SkillImporter
    ) -> None:
        """MANIFEST.json provides source_url as fallback since SKILL.md doesn't have it."""
        zip_bytes = _make_zip({
            "morning-digest/SKILL.md": _EXTENDED_SKILL_MD,
            "morning-digest/MANIFEST.json": json.dumps(_MANIFEST_JSON),
        })
        result = importer.import_from_zip(zip_bytes)
        # SKILL.md takes precedence for license/category/tags
        assert result["license"] == "Apache-2.0"
        assert result["category"] == "communication"
        assert result["tags"] == ["productivity", "morning"]
        # MANIFEST provides source_url (not in SKILL.md)
        assert result["source_url"] == "https://example.com/morning-digest"

    def test_zip_with_invalid_manifest_json_still_imports(
        self, importer: SkillImporter
    ) -> None:
        """Invalid MANIFEST.json is tolerated; skill still imports from SKILL.md."""
        zip_bytes = _make_zip({
            "SKILL.md": _VALID_SKILL_MD,
            "MANIFEST.json": "not valid json {{{",
        })
        result = importer.import_from_zip(zip_bytes)
        assert result["name"] == "email_digest"

    def test_zip_with_assets_dir_is_ignored(self, importer: SkillImporter) -> None:
        """assets/ directory in ZIP is silently ignored."""
        zip_bytes = _make_zip({
            "SKILL.md": _VALID_SKILL_MD,
            "assets/.gitkeep": "",
        })
        result = importer.import_from_zip(zip_bytes)
        assert result["name"] == "email_digest"

    def test_zip_extended_frontmatter_fields_parsed(
        self, importer: SkillImporter
    ) -> None:
        zip_bytes = _make_zip({"SKILL.md": _EXTENDED_SKILL_MD})
        result = importer.import_from_zip(zip_bytes)
        assert result["license"] == "Apache-2.0"
        assert result["allowed_tools"] == ["email.fetch", "calendar.list"]
        assert result["tags"] == ["productivity", "morning"]


# ── SKSEC-01: Dependency declaration parsing ─────────────────────────────────

_SKILL_MD_WITH_DEPS_LIST = """---
name: dep_skill
description: Skill with dependency list
dependencies:
  - requests
  - httpx
---
Some instructions.
"""

_SKILL_MD_WITH_DEPS_STRING = """---
name: dep_skill_str
description: Skill with dependency string
dependencies: "requests httpx"
---
Some instructions.
"""

_SKILL_MD_WITHOUT_DEPS = """---
name: no_dep_skill
description: Skill with no dependencies
---
Some instructions.
"""


class TestDependencyParsing:
    """Tests for SKSEC-01: parsing declared_dependencies from frontmatter and ZIP."""

    def test_dependencies_list_parsed(self, importer: SkillImporter) -> None:
        """dependencies: [requests, httpx] in frontmatter -> declared_dependencies list."""
        result = importer.parse_skill_md(_SKILL_MD_WITH_DEPS_LIST)
        assert result["declared_dependencies"] == ["requests", "httpx"]

    def test_dependencies_string_parsed(self, importer: SkillImporter) -> None:
        """dependencies: 'requests httpx' string -> declared_dependencies list."""
        result = importer.parse_skill_md(_SKILL_MD_WITH_DEPS_STRING)
        assert result["declared_dependencies"] == ["requests", "httpx"]

    def test_no_dependencies_field(self, importer: SkillImporter) -> None:
        """No dependencies: key -> declared_dependencies absent (or empty)."""
        result = importer.parse_skill_md(_SKILL_MD_WITHOUT_DEPS)
        assert "declared_dependencies" not in result or result.get("declared_dependencies") == []

    def test_dependencies_from_requirements_txt_in_zip(
        self, importer: SkillImporter
    ) -> None:
        """ZIP with scripts/requirements.txt (no frontmatter deps) -> declared_dependencies from file."""
        req_content = "requests==2.31.0\nhttpx>=0.27.0\n# comment\n\n"
        zip_bytes = _make_zip({
            "SKILL.md": _SKILL_MD_WITHOUT_DEPS,
            "scripts/requirements.txt": req_content,
        })
        result = importer.import_from_zip(zip_bytes)
        assert result["declared_dependencies"] == ["requests", "httpx"]

    def test_frontmatter_deps_take_priority_over_requirements_txt(
        self, importer: SkillImporter
    ) -> None:
        """Frontmatter dependencies: takes precedence over scripts/requirements.txt."""
        req_content = "requests\n"
        zip_bytes = _make_zip({
            "SKILL.md": _SKILL_MD_WITH_DEPS_LIST,  # has [requests, httpx]
            "scripts/requirements.txt": "flask\n",  # different package
        })
        result = importer.import_from_zip(zip_bytes)
        # Frontmatter wins: [requests, httpx], not [flask]
        assert result["declared_dependencies"] == ["requests", "httpx"]


# ── SKSEC-01: scripts/ extraction from ZIP ───────────────────────────────────

_SKILL_MD_BASIC = """---
name: scripted_skill
description: Skill with scripts
dependencies:
  - requests
---
Some instructions.
"""


class TestZipScripts:
    """Tests for SKSEC-01: extracting scripts/ .py content from ZIP bundles."""

    def test_scripts_py_extracted(self, importer: SkillImporter) -> None:
        """scripts/helper.py in ZIP -> scripts_content with filename and source."""
        helper_src = "import requests\nprint('hello')\n"
        zip_bytes = _make_zip({
            "SKILL.md": _SKILL_MD_BASIC,
            "scripts/helper.py": helper_src,
        })
        result = importer.import_from_zip(zip_bytes)
        assert "scripts_content" in result
        assert len(result["scripts_content"]) == 1
        assert result["scripts_content"][0]["filename"] == "helper.py"
        assert result["scripts_content"][0]["source"] == helper_src

    def test_no_scripts_directory_empty_list(self, importer: SkillImporter) -> None:
        """ZIP with no scripts/ dir -> scripts_content absent or empty."""
        zip_bytes = _make_zip({"SKILL.md": _VALID_SKILL_MD})
        result = importer.import_from_zip(zip_bytes)
        # Either absent or empty list is acceptable
        assert result.get("scripts_content", []) == []

    def test_non_py_files_in_scripts_ignored(self, importer: SkillImporter) -> None:
        """scripts/readme.txt in ZIP is NOT included in scripts_content."""
        zip_bytes = _make_zip({
            "SKILL.md": _SKILL_MD_BASIC,
            "scripts/readme.txt": "This is documentation.",
        })
        result = importer.import_from_zip(zip_bytes)
        assert result.get("scripts_content", []) == []

    def test_undeclared_import_triggers_rejection(
        self, importer: SkillImporter
    ) -> None:
        """Integration: skill with undeclared 'paramiko' import -> SecurityScanner rejects."""
        skill_md = """---
name: unsafe_skill
description: Skill that uses undeclared paramiko
---
Some instructions.
"""
        # scripts/tool.py imports paramiko but it's NOT declared in frontmatter
        tool_src = "import paramiko\nprint('connecting')\n"
        zip_bytes = _make_zip({
            "SKILL.md": skill_md,
            "scripts/tool.py": tool_src,
        })
        skill_data = importer.import_from_zip(zip_bytes)
        scanner = SecurityScanner()
        report = scanner.scan(skill_data)
        assert report.recommendation == "reject"


# ── Claude Code YAML import ───────────────────────────────────────────────────


_CLAUDE_CODE_YAML = """
name: morning_digest
description: Sends a morning summary of emails and calendar events to keep you on track.
when_to_use: Use this skill at the start of the workday to get a quick overview.
trigger: /morning or when user says "morning briefing"
tools:
  - email.fetch
  - calendar.list
  - llm.summarize
category: productivity
"""


def test_import_claude_code_yaml(importer: SkillImporter) -> None:
    """Claude Code YAML with name/description/tools is correctly mapped to agentskills fields."""
    result = importer.import_from_claude_code_yaml(_CLAUDE_CODE_YAML)

    assert result["name"] == "morning_digest"
    assert "Sends a morning summary" in result["description"]
    assert isinstance(result["instruction_markdown"], str)
    assert len(result["instruction_markdown"]) > 0
    assert isinstance(result["allowed_tools"], list)
    assert "email.fetch" in result["allowed_tools"]
    assert result["skill_type"] == "instructional"


def test_github_raw_url_conversion(importer: SkillImporter) -> None:
    """GitHub blob URL is converted to raw.githubusercontent.com before fetching."""
    github_url = "https://github.com/user/repo/blob/main/skill.yaml"
    raw_url = SkillImporter._github_to_raw_url(github_url)
    assert raw_url == "https://raw.githubusercontent.com/user/repo/main/skill.yaml"
