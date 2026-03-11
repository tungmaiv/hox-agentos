# Skill Import Adapter Framework

## Overview

A pluggable adapter architecture for importing skills from multiple sources (AgentSkills repositories, Claude Code marketplace, ZIP files, GitHub repos, etc.) through a unified interface.

## Problem Statement

Current implementation:
- Hardcoded to AgentSkills format only
- Cannot import from Claude marketplace
- No support for other skill formats
- Adding new sources requires core code changes

## Solution: Adapter Pattern

```
┌─────────────────────────────────────────────────────────────┐
│              Unified Import Service                          │
│         (Single API for all import sources)                 │
└──────────────┬──────────────────────────────────────────────┘
               │
    ┌──────────┼──────────┬───────────────┐
    │          │          │               │
    ▼          ▼          ▼               ▼
┌────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐
│ Skill  │ │ Claude │ │   ZIP    │ │  GitHub  │
│ Repo   │ │ Market │ │  File    │ │   Repo   │
│Adapter │ │Adapter │ │ Adapter  │ │ Adapter  │
└────────┘ └────────┘ └──────────┘ └──────────┘
```

## Core Components

### 1. Base Adapter Interface

**File:** `backend/skills/adapters/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, List

class ImportSourceType(str, Enum):
    """Enumeration of supported import source types."""
    SKILL_REPO = "skill_repo"           # AgentSkills repository
    CLAUDE_MARKET = "claude_market"     # Claude Code marketplace
    ZIP_FILE = "zip_file"               # Local ZIP file upload
    DIRECT_URL = "direct_url"           # Direct SKILL.md URL
    GITHUB_REPO = "github_repo"         # Raw GitHub repository

@dataclass
class SkillAsset:
    """Represents a file asset associated with a skill."""
    asset_type: str          # "template", "script", "reference", "command"
    filename: str
    content: str
    content_type: str = "text"  # "text" or "binary"

@dataclass
class SkillCommand:
    """Represents a slash command within a skill."""
    command_name: str
    description: str
    prompt_template: str
    order_index: int = 0

@dataclass
class NormalizedSkill:
    """Common normalized format for all skill imports.
    
    All adapters must convert their source format to this standard structure.
    """
    # Core fields (required)
    name: str
    description: str
    version: str
    skill_type: str              # "instructional" | "procedural"
    
    # Optional fields
    slash_command: Optional[str] = None
    instruction_markdown: Optional[str] = None
    procedure_json: Optional[List[dict]] = None
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None
    
    # Metadata
    license: Optional[str] = None
    compatibility: Optional[str] = None
    metadata_json: Optional[dict] = None
    allowed_tools: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    category: Optional[str] = None
    
    # Source tracking
    source_url: Optional[str] = None
    source_type: ImportSourceType = ImportSourceType.DIRECT_URL
    
    # Extended features
    assets: Optional[List[SkillAsset]] = None
    commands: Optional[List[SkillCommand]] = None

class SkillImportError(Exception):
    """Raised when skill import fails."""
    pass

class SkillAdapter(ABC):
    """Abstract base class for all skill import adapters.
    
    All skill import sources must implement this interface to be
    registered with the AdapterRegistry.
    """
    
    @property
    @abstractmethod
    def source_type(self) -> ImportSourceType:
        """Return the type of import source this adapter handles."""
        pass
    
    @abstractmethod
    async def can_handle(self, source: str, **kwargs) -> bool:
        """Check if this adapter can handle the given source.
        
        This method should quickly determine if the source matches
        this adapter's format without doing heavy processing.
        
        Args:
            source: URL, path, or identifier for the skill source
            **kwargs: Additional context (auth tokens, timeout, etc.)
        
        Returns:
            True if this adapter can import from this source
        """
        pass
    
    @abstractmethod
    async def validate_source(self, source: str, **kwargs) -> dict:
        """Validate source exists and return metadata preview.
        
        Used for showing skill info before import (UI preview).
        
        Args:
            source: URL, path, or identifier
            **kwargs: Additional parameters
        
        Returns:
            Dict with keys: name, description, version, skill_count, etc.
        """
        pass
    
    @abstractmethod
    async def fetch_and_normalize(self, source: str, **kwargs) -> NormalizedSkill:
        """Fetch skill from source and convert to normalized format.
        
        This is the main import method. It should:
        1. Fetch skill data from source
        2. Parse source-specific format
        3. Convert to NormalizedSkill
        4. Extract any assets or commands
        
        Args:
            source: URL, path, or identifier
            **kwargs: Additional parameters (skill_name for repos, etc.)
        
        Returns:
            NormalizedSkill in common format
        
        Raises:
            SkillImportError: If import fails
        """
        pass
    
    @abstractmethod
    async def get_skill_list(self, source: str, **kwargs) -> List[dict]:
        """List available skills from this source.
        
        Used for browsing repositories or marketplaces.
        
        Args:
            source: URL or identifier for the source
            **kwargs: Additional parameters
        
        Returns:
            List of skill metadata dicts
        """
        pass
```

### 2. Adapter Registry

**File:** `backend/skills/adapters/registry.py`

```python
from typing import Type, Optional, Dict, List
import structlog

from skills.adapters.base import SkillAdapter, ImportSourceType

logger = structlog.get_logger(__name__)

class AdapterRegistry:
    """Central registry for all skill import adapters.
    
    This registry manages adapter instances and provides:
    - Adapter lookup by source type
    - Auto-detection of appropriate adapter
    - Registration of new adapters
    """
    
    _adapters: Dict[ImportSourceType, Type[SkillAdapter]] = {}
    _instances: Dict[ImportSourceType, SkillAdapter] = {}
    
    @classmethod
    def register(
        cls, 
        source_type: ImportSourceType, 
        adapter_class: Type[SkillAdapter]
    ) -> None:
        """Register an adapter class for a source type.
        
        Args:
            source_type: The type this adapter handles
            adapter_class: The adapter class (not instance)
        
        Example:
            AdapterRegistry.register(
                ImportSourceType.CLAUDE_MARKET, 
                ClaudeMarketAdapter
            )
        """
        cls._adapters[source_type] = adapter_class
        # Clear cached instance if re-registering
        cls._instances.pop(source_type, None)
        logger.info(
            "adapter_registered",
            source_type=source_type.value,
            adapter_class=adapter_class.__name__
        )
    
    @classmethod
    def get(cls, source_type: ImportSourceType) -> Optional[SkillAdapter]:
        """Get adapter instance by source type.
        
        Returns cached instance or creates new one.
        """
        if source_type not in cls._instances:
            adapter_class = cls._adapters.get(source_type)
            if adapter_class:
                cls._instances[source_type] = adapter_class()
                logger.debug(
                    "adapter_instance_created",
                    source_type=source_type.value
                )
        
        return cls._instances.get(source_type)
    
    @classmethod
    async def detect_adapter(cls, source: str, **kwargs) -> Optional[SkillAdapter]:
        """Auto-detect the appropriate adapter for a source.
        
        Iterates through all registered adapters and returns the first
        one that can_handle() returns True for.
        
        Args:
            source: URL, path, or identifier
            **kwargs: Additional context
        
        Returns:
            First matching adapter or None
        """
        for source_type in ImportSourceType:
            adapter = cls.get(source_type)
            if adapter:
                try:
                    if await adapter.can_handle(source, **kwargs):
                        logger.info(
                            "adapter_detected",
                            source=source[:100],  # Truncate for logging
                            source_type=source_type.value
                        )
                        return adapter
                except Exception as e:
                    logger.warning(
                        "adapter_detection_failed",
                        source_type=source_type.value,
                        error=str(e)
                    )
                    continue
        
        logger.warning("no_adapter_found", source=source[:100])
        return None
    
    @classmethod
    def list_registered(cls) -> List[ImportSourceType]:
        """List all registered adapter types."""
        return list(cls._adapters.keys())
    
    @classmethod
    def unregister(cls, source_type: ImportSourceType) -> None:
        """Unregister an adapter (mainly for testing)."""
        cls._adapters.pop(source_type, None)
        cls._instances.pop(source_type, None)

# Convenience function for importing
def get_adapter(source_type: ImportSourceType) -> Optional[SkillAdapter]:
    """Get adapter by source type."""
    return AdapterRegistry.get(source_type)
```

### 3. Skill Repo Adapter (Refactored)

**File:** `backend/skills/adapters/skill_repo_adapter.py`

```python
import httpx
from typing import List, Any

from skills.adapters.base import (
    SkillAdapter, 
    ImportSourceType, 
    NormalizedSkill,
    SkillImportError
)
from skills.importer import SkillImporter

class SkillRepoAdapter(SkillAdapter):
    """Adapter for AgentSkills format repositories.
    
    Handles repositories that serve agentskills-index.json
    with SKILL.md files for each skill.
    """
    
    @property
    def source_type(self) -> ImportSourceType:
        return ImportSourceType.SKILL_REPO
    
    async def can_handle(self, source: str, **kwargs) -> bool:
        """Check if source has agentskills-index.json."""
        if not source.startswith(("http://", "https://")):
            return False
        
        try:
            index_url = f"{source.rstrip('/')}/agentskills-index.json"
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.head(index_url)
                return response.status_code == 200
        except Exception:
            return False
    
    async def validate_source(self, source: str, **kwargs) -> dict:
        """Fetch and return repository metadata."""
        index = await self._fetch_index(source)
        
        return {
            "name": index["repository"]["name"],
            "description": index["repository"].get("description", ""),
            "version": index["repository"].get("version", "0.0.0"),
            "url": source,
            "skill_count": len(index.get("skills", [])),
            "skills": [
                {
                    "name": s["name"],
                    "description": s.get("description", ""),
                    "category": s.get("category"),
                    "tags": s.get("tags", []),
                }
                for s in index.get("skills", [])
            ]
        }
    
    async def fetch_and_normalize(
        self, 
        source: str, 
        skill_name: str,
        **kwargs
    ) -> NormalizedSkill:
        """Import specific skill from repository."""
        # 1. Fetch repository index
        index = await self._fetch_index(source)
        
        # 2. Find skill in index
        skill_entry = next(
            (s for s in index.get("skills", []) if s["name"] == skill_name),
            None
        )
        
        if not skill_entry:
            raise SkillImportError(
                f"Skill '{skill_name}' not found in repository"
            )
        
        # 3. Fetch SKILL.md content
        skill_url = skill_entry.get("skill_url")
        if not skill_url:
            raise SkillImportError(f"No skill_url for '{skill_name}'")
        
        importer = SkillImporter()
        skill_data = await importer.import_from_url(skill_url)
        
        # 4. Normalize to common format
        return NormalizedSkill(
            name=skill_data["name"],
            description=skill_data["description"],
            version=skill_data.get("version", "1.0.0"),
            skill_type=skill_data.get("skill_type", "instructional"),
            slash_command=skill_data.get("slash_command"),
            instruction_markdown=skill_data.get("instruction_markdown"),
            procedure_json=skill_data.get("procedure_json"),
            input_schema=skill_data.get("input_schema"),
            output_schema=skill_data.get("output_schema"),
            license=skill_data.get("license"),
            compatibility=skill_data.get("compatibility"),
            metadata_json={
                **(skill_data.get("metadata_json") or {}),
                "repository_name": index["repository"]["name"],
            },
            allowed_tools=skill_data.get("allowed_tools"),
            tags=skill_data.get("tags"),
            category=skill_data.get("category"),
            source_url=skill_url,
            source_type=ImportSourceType.SKILL_REPO,
        )
    
    async def get_skill_list(self, source: str, **kwargs) -> List[dict]:
        """List all skills in repository."""
        index = await self._fetch_index(source)
        return index.get("skills", [])
    
    async def _fetch_index(self, source: str) -> dict:
        """Fetch agentskills-index.json from repository."""
        base = source.rstrip("/")
        index_url = f"{base}/agentskills-index.json"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(index_url)
            response.raise_for_status()
            return response.json()
```

### 4. Claude Marketplace Adapter

**File:** `backend/skills/adapters/claude_market_adapter.py`

```python
import io
import json
import os
import re
import zipfile
from typing import List
import base64

import httpx

from skills.adapters.base import (
    SkillAdapter,
    ImportSourceType,
    NormalizedSkill,
    SkillAsset,
    SkillCommand,
    SkillImportError
)

class ClaudeMarketAdapter(SkillAdapter):
    """Adapter for Claude Code marketplace skills (GitHub-based).
    
    Claude marketplace skills are GitHub repos with:
    - .claude-plugin/plugin.json (manifest)
    - plugins/{skill-name}/SKILL.md (main skill file)
    - plugins/{skill-name}/commands/ (slash commands)
    - plugins/{skill-name}/templates/ (HTML templates)
    - plugins/{skill-name}/references/ (reference docs)
    - plugins/{skill-name}/scripts/ (utility scripts)
    """
    
    @property
    def source_type(self) -> ImportSourceType:
        return ImportSourceType.CLAUDE_MARKET
    
    async def can_handle(self, source: str, **kwargs) -> bool:
        """Check if source is a GitHub repo with .claude-plugin/."""
        if not source.startswith("https://github.com/"):
            return False
        
        try:
            api_url = self._github_url_to_api(source)
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check for .claude-plugin directory
                response = await client.get(
                    f"{api_url}/contents/.claude-plugin",
                    headers={"Accept": "application/vnd.github+json"}
                )
                return response.status_code == 200
        except Exception:
            return False
    
    async def validate_source(self, source: str, **kwargs) -> dict:
        """Fetch plugin.json and return metadata."""
        api_url = self._github_url_to_api(source)
        
        async with httpx.AsyncClient() as client:
            # Fetch plugin.json
            response = await client.get(
                f"{api_url}/contents/.claude-plugin/plugin.json",
                headers={"Accept": "application/vnd.github+json"}
            )
            response.raise_for_status()
            
            data = response.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            plugin = json.loads(content)
        
        return {
            "name": plugin.get("name"),
            "description": plugin.get("description"),
            "version": plugin.get("version"),
            "author": plugin.get("author"),
            "license": plugin.get("license"),
            "command_count": len(plugin.get("commands", [])),
            "commands": [
                {
                    "name": cmd.get("name"),
                    "description": cmd.get("description")
                }
                for cmd in plugin.get("commands", [])
            ]
        }
    
    async def fetch_and_normalize(self, source: str, **kwargs) -> NormalizedSkill:
        """Import skill from Claude marketplace."""
        # 1. Download ZIP from GitHub
        zip_bytes = await self._download_repo_zip(source)
        
        # 2. Extract and parse
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # Find SKILL.md (usually in plugins/{name}/)
            skill_md_path = self._find_skill_md(zf)
            skill_md_content = zf.read(skill_md_path).decode("utf-8")
            
            # Parse frontmatter and body
            frontmatter, body = self._parse_skill_md(skill_md_content)
            
            # Extract commands
            commands = self._extract_commands(zf, skill_md_path)
            
            # Extract assets
            assets = self._extract_assets(zf, skill_md_path)
            
            # Inline references into body
            body = self._inline_references(body, zf, skill_md_path)
        
        # 3. Normalize to common format
        metadata = frontmatter.get("metadata", {})
        
        return NormalizedSkill(
            name=frontmatter["name"],
            description=frontmatter["description"],
            version=metadata.get("version", "1.0.0"),
            skill_type="instructional",
            slash_command=commands[0].command_name if commands else None,
            instruction_markdown=body,
            license=frontmatter.get("license"),
            compatibility=frontmatter.get("compatibility"),
            metadata_json={
                "author": metadata.get("author"),
                "source": "claude_marketplace",
                "original_repo": source,
            },
            source_url=source,
            source_type=ImportSourceType.CLAUDE_MARKET,
            assets=assets if assets else None,
            commands=commands if commands else None,
        )
    
    async def get_skill_list(self, source: str, **kwargs) -> List[dict]:
        """Claude marketplace repos typically have one skill."""
        preview = await self.validate_source(source, **kwargs)
        return [{
            "name": preview["name"],
            "description": preview["description"],
            "category": "claude_marketplace"
        }]
    
    def _github_url_to_api(self, github_url: str) -> str:
        """Convert GitHub URL to API URL."""
        match = re.match(r"https://github\.com/([^/]+)/([^/]+)", github_url)
        if not match:
            raise ValueError(f"Invalid GitHub URL: {github_url}")
        return f"https://api.github.com/repos/{match.group(1)}/{match.group(2)}"
    
    async def _download_repo_zip(self, github_url: str) -> bytes:
        """Download repository as ZIP."""
        match = re.match(r"https://github\.com/([^/]+)/([^/]+)", github_url)
        if not match:
            raise ValueError(f"Invalid GitHub URL: {github_url}")
        
        owner, repo = match.groups()
        
        # Try main branch first, then master
        for branch in ["main", "master"]:
            zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(zip_url)
                if response.status_code == 200:
                    return response.content
        
        raise SkillImportError(f"Could not download repository ZIP: {github_url}")
    
    def _find_skill_md(self, zf: zipfile.ZipFile) -> str:
        """Find SKILL.md in ZIP archive."""
        for name in zf.namelist():
            if name.endswith("SKILL.md"):
                return name
        raise SkillImportError("SKILL.md not found in archive")
    
    def _parse_skill_md(self, content: str) -> tuple:
        """Parse YAML frontmatter and markdown body."""
        import yaml
        
        # Match ---\n...\n--- pattern
        match = re.match(r"^---\n(.*?)\n---\n?(.*)", content, re.DOTALL)
        if not match:
            raise SkillImportError("Invalid SKILL.md: missing YAML frontmatter")
        
        yaml_text = match.group(1)
        body_text = match.group(2).strip()
        
        frontmatter = yaml.safe_load(yaml_text)
        if not isinstance(frontmatter, dict):
            raise SkillImportError("YAML frontmatter must be a mapping")
        
        return frontmatter, body_text
    
    def _extract_commands(self, zf: zipfile.ZipFile, skill_md_path: str) -> List[SkillCommand]:
        """Extract commands from commands/ directory."""
        commands = []
        base_dir = os.path.dirname(skill_md_path)
        commands_dir = f"{base_dir}/commands/"
        
        for name in zf.namelist():
            if name.startswith(commands_dir) and name.endswith(".md"):
                content = zf.read(name).decode("utf-8")
                cmd_name = os.path.basename(name).replace(".md", "")
                
                # Extract first line as description
                first_line = content.split("\n")[0].strip("# ")
                
                commands.append(SkillCommand(
                    command_name=cmd_name,
                    description=first_line,
                    prompt_template=content,
                    order_index=len(commands)
                ))
        
        return commands
    
    def _extract_assets(self, zf: zipfile.ZipFile, skill_md_path: str) -> List[SkillAsset]:
        """Extract assets from templates/, references/, scripts/."""
        assets = []
        base_dir = os.path.dirname(skill_md_path)
        
        asset_dirs = {
            "templates": "template",
            "references": "reference",
            "scripts": "script"
        }
        
        for dir_name, asset_type in asset_dirs.items():
            dir_path = f"{base_dir}/{dir_name}/"
            
            for name in zf.namelist():
                if name.startswith(dir_path) and not name.endswith("/"):
                    content = zf.read(name)
                    filename = os.path.basename(name)
                    
                    # Determine content type
                    content_type = "text"
                    if any(name.endswith(ext) for ext in [".png", ".jpg", ".gif", ".zip"]):
                        content_type = "binary"
                        content = base64.b64encode(content).decode()
                    else:
                        content = content.decode("utf-8")
                    
                    assets.append(SkillAsset(
                        asset_type=asset_type,
                        filename=filename,
                        content=content,
                        content_type=content_type
                    ))
        
        return assets
    
    def _inline_references(self, body: str, zf: zipfile.ZipFile, skill_md_path: str) -> str:
        """Inline reference files into skill body."""
        base_dir = os.path.dirname(skill_md_path)
        refs_dir = f"{base_dir}/references/"
        
        inlined = "\n\n## Reference Materials\n\n"
        has_refs = False
        
        for name in zf.namelist():
            if name.startswith(refs_dir) and name.endswith(".md"):
                has_refs = True
                content = zf.read(name).decode("utf-8")
                ref_name = os.path.basename(name)
                inlined += f"\n### {ref_name}\n\n{content}\n"
        
        if has_refs:
            return body + inlined
        return body
```

### 5. ZIP File Adapter

**File:** `backend/skills/adapters/zip_adapter.py`

```python
from typing import BinaryIO, Union

from skills.adapters.base import (
    SkillAdapter,
    ImportSourceType,
    NormalizedSkill,
    SkillImportError
)
from skills.importer import SkillImporter

class ZipFileAdapter(SkillAdapter):
    """Adapter for direct ZIP file uploads."""
    
    @property
    def source_type(self) -> ImportSourceType:
        return ImportSourceType.ZIP_FILE
    
    async def can_handle(self, source: Union[str, bytes, BinaryIO], **kwargs) -> bool:
        """Check if source is valid ZIP data."""
        try:
            if isinstance(source, str):
                # Try to open as file path
                with open(source, 'rb') as f:
                    import zipfile
                    zipfile.ZipFile(f)
            elif isinstance(source, bytes):
                import io
                import zipfile
                zipfile.ZipFile(io.BytesIO(source))
            else:
                # Assume it's a file-like object
                import zipfile
                zipfile.ZipFile(source)
            return True
        except Exception:
            return False
    
    async def validate_source(self, source: Union[str, bytes], **kwargs) -> dict:
        """Validate ZIP contains SKILL.md."""
        import io
        import zipfile
        
        if isinstance(source, str):
            zf = zipfile.ZipFile(source)
        else:
            zf = zipfile.ZipFile(io.BytesIO(source))
        
        with zf:
            has_skill_md = any(
                name.endswith("SKILL.md") for name in zf.namelist()
            )
            
            if not has_skill_md:
                raise SkillImportError("ZIP must contain SKILL.md")
            
            # Try to parse SKILL.md for preview
            skill_md_name = next(
                name for name in zf.namelist() if name.endswith("SKILL.md")
            )
            content = zf.read(skill_md_name).decode("utf-8")
            
            # Parse frontmatter for preview
            import yaml
            match = __import__('re').match(
                r"^---\n(.*?)\n---", content, __import__('re').DOTALL
            )
            if match:
                frontmatter = yaml.safe_load(match.group(1))
                return {
                    "name": frontmatter.get("name", "Unknown"),
                    "description": frontmatter.get("description", ""),
                    "version": frontmatter.get("version", "1.0.0"),
                }
            
            return {"name": "Unknown", "description": "Invalid SKILL.md format"}
    
    async def fetch_and_normalize(
        self, 
        source: Union[str, bytes], 
        **kwargs
    ) -> NormalizedSkill:
        """Import from ZIP file."""
        importer = SkillImporter()
        
        if isinstance(source, str):
            with open(source, 'rb') as f:
                skill_data = importer.import_from_zip(f.read())
        else:
            skill_data = importer.import_from_zip(source)
        
        return NormalizedSkill(
            name=skill_data["name"],
            description=skill_data["description"],
            version=skill_data.get("version", "1.0.0"),
            skill_type=skill_data.get("skill_type", "instructional"),
            slash_command=skill_data.get("slash_command"),
            instruction_markdown=skill_data.get("instruction_markdown"),
            procedure_json=skill_data.get("procedure_json"),
            input_schema=skill_data.get("input_schema"),
            output_schema=skill_data.get("output_schema"),
            license=skill_data.get("license"),
            compatibility=skill_data.get("compatibility"),
            metadata_json=skill_data.get("metadata_json"),
            allowed_tools=skill_data.get("allowed_tools"),
            tags=skill_data.get("tags"),
            category=skill_data.get("category"),
            source_url="local_zip_upload",
            source_type=ImportSourceType.ZIP_FILE,
        )
    
    async def get_skill_list(self, source: str, **kwargs) -> list:
        """ZIP files contain single skill."""
        preview = await self.validate_source(source, **kwargs)
        return [preview]
```

### 6. Unified Import Service

**File:** `backend/skills/import_service.py`

```python
from typing import Optional, Union
from uuid import UUID
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.skill_definition import SkillDefinition
from skills.adapters.base import ImportSourceType, NormalizedSkill
from skills.adapters.registry import AdapterRegistry
from skills.security_scanner import SecurityScanner, SecurityReport

logger = structlog.get_logger(__name__)

class UnifiedImportService:
    """Unified service for importing skills from any source.
    
    This service provides a single API for importing skills regardless
    of their source format (AgentSkills, Claude marketplace, ZIP, etc.).
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.security_scanner = SecurityScanner()
    
    async def import_skill(
        self,
        source: str,
        user_id: UUID,
        source_type: Optional[ImportSourceType] = None,
        skill_name: Optional[str] = None,
        **kwargs
    ) -> SkillDefinition:
        """Import a skill from any supported source.
        
        This is the main entry point for skill imports. It will:
        1. Detect or use specified adapter
        2. Fetch and normalize skill data
        3. Run security scan
        4. Store skill in database
        5. Handle assets and commands if present
        
        Args:
            source: URL, path, or raw data for the skill source
            user_id: ID of user performing the import
            source_type: Optional explicit source type (auto-detected if None)
            skill_name: Required for repository sources (specifies which skill)
            **kwargs: Additional adapter-specific parameters
        
        Returns:
            Created SkillDefinition instance
        
        Raises:
            ValueError: If no adapter found or invalid parameters
            SkillImportError: If import fails
        """
        logger.info(
            "skill_import_started",
            source=source[:100] if isinstance(source, str) else "binary",
            source_type=source_type.value if source_type else None,
            user_id=str(user_id)
        )
        
        # 1. Get appropriate adapter
        if source_type:
            adapter = AdapterRegistry.get(source_type)
            if not adapter:
                raise ValueError(f"No adapter registered for type: {source_type}")
        else:
            adapter = await AdapterRegistry.detect_adapter(source, **kwargs)
            if not adapter:
                raise ValueError(f"Cannot detect adapter for source: {source}")
        
        logger.info("adapter_selected", adapter_type=adapter.source_type.value)
        
        # 2. Fetch and normalize
        normalized = await adapter.fetch_and_normalize(
            source, skill_name=skill_name, **kwargs
        )
        
        logger.info(
            "skill_normalized",
            name=normalized.name,
            skill_type=normalized.skill_type,
            has_assets=normalized.assets is not None,
            command_count=len(normalized.commands) if normalized.commands else 0
        )
        
        # 3. Security scan
        report = await self.security_scanner.scan(
            normalized.__dict__,
            source_url=normalized.source_url
        )
        
        logger.info(
            "security_scan_complete",
            score=report.score,
            recommendation=report.recommendation
        )
        
        # 4. Create SkillDefinition
        skill = await self._create_skill_definition(normalized, report, user_id)
        
        # 5. Store assets if present
        if normalized.assets:
            await self._store_assets(skill.id, normalized.assets)
        
        # 6. Store commands if present (multi-command skill)
        if normalized.commands:
            await self._store_commands(skill.id, normalized.commands)
        
        logger.info(
            "skill_import_complete",
            skill_id=str(skill.id),
            name=skill.name,
            status=skill.status
        )
        
        return skill
    
    async def preview_skill(
        self,
        source: str,
        source_type: Optional[ImportSourceType] = None,
        **kwargs
    ) -> dict:
        """Preview skill metadata before importing.
        
        Returns metadata without actually importing the skill.
        Useful for UI previews before user confirmation.
        
        Args:
            source: URL, path, or identifier
            source_type: Optional explicit source type
            **kwargs: Additional adapter parameters
        
        Returns:
            Dict with skill metadata
        """
        if source_type:
            adapter = AdapterRegistry.get(source_type)
        else:
            adapter = await AdapterRegistry.detect_adapter(source, **kwargs)
        
        if not adapter:
            raise ValueError(f"Cannot detect adapter for source: {source}")
        
        return await adapter.validate_source(source, **kwargs)
    
    async def list_available_skills(
        self,
        source: str,
        source_type: Optional[ImportSourceType] = None,
        **kwargs
    ) -> list:
        """List available skills from a source.
        
        Used for browsing repositories or marketplaces.
        
        Args:
            source: URL or identifier for the source
            source_type: Optional explicit source type
            **kwargs: Additional parameters
        
        Returns:
            List of skill metadata dicts
        """
        if source_type:
            adapter = AdapterRegistry.get(source_type)
        else:
            adapter = await AdapterRegistry.detect_adapter(source, **kwargs)
        
        if not adapter:
            raise ValueError(f"Cannot detect adapter for source: {source}")
        
        return await adapter.get_skill_list(source, **kwargs)
    
    async def _create_skill_definition(
        self,
        normalized: NormalizedSkill,
        report: SecurityReport,
        user_id: UUID
    ) -> SkillDefinition:
        """Create SkillDefinition from normalized data."""
        skill = SkillDefinition(
            name=normalized.name,
            display_name=normalized.name,  # Could be enhanced
            description=normalized.description,
            version=normalized.version,
            skill_type=normalized.skill_type,
            slash_command=normalized.slash_command,
            source_type="imported",
            instruction_markdown=normalized.instruction_markdown,
            procedure_json=normalized.procedure_json,
            input_schema=normalized.input_schema,
            output_schema=normalized.output_schema,
            license=normalized.license,
            compatibility=normalized.compatibility,
            metadata_json={
                **(normalized.metadata_json or {}),
                "import_source": normalized.source_type.value,
                "adapter_version": "1.0.0",
                "imported_at": datetime.now(timezone.utc).isoformat(),
            },
            allowed_tools=normalized.allowed_tools,
            tags=normalized.tags,
            category=normalized.category,
            source_url=normalized.source_url,
            status="pending_review",
            is_active=False,
            security_score=report.score,
            security_report={
                "score": report.score,
                "factors": report.factors,
                "recommendation": report.recommendation,
                "injection_matches": report.injection_matches,
            },
            created_by=user_id,
        )
        
        self.session.add(skill)
        await self.session.commit()
        await self.session.refresh(skill)
        
        return skill
    
    async def _store_assets(
        self,
        skill_id: UUID,
        assets: list
    ) -> None:
        """Store skill assets (for future asset management)."""
        # TODO: Implement asset storage
        # For now, assets are stored in skill_assets table or S3
        logger.info(
            "assets_stored",
            skill_id=str(skill_id),
            asset_count=len(assets)
        )
    
    async def _store_commands(
        self,
        skill_id: UUID,
        commands: list
    ) -> None:
        """Store skill commands (for future multi-command support)."""
        # TODO: Implement command storage
        # For now, commands are embedded in metadata
        logger.info(
            "commands_stored",
            skill_id=str(skill_id),
            command_count=len(commands)
        )
```

## Registration

**File:** `backend/skills/adapters/__init__.py`

```python
"""Skill import adapters package."""

from skills.adapters.base import (
    SkillAdapter,
    ImportSourceType,
    NormalizedSkill,
    SkillAsset,
    SkillCommand,
    SkillImportError
)
from skills.adapters.registry import AdapterRegistry, get_adapter

# Import and register default adapters
from skills.adapters.skill_repo_adapter import SkillRepoAdapter
from skills.adapters.claude_market_adapter import ClaudeMarketAdapter
from skills.adapters.zip_adapter import ZipFileAdapter

# Register adapters
AdapterRegistry.register(ImportSourceType.SKILL_REPO, SkillRepoAdapter)
AdapterRegistry.register(ImportSourceType.CLAUDE_MARKET, ClaudeMarketAdapter)
AdapterRegistry.register(ImportSourceType.ZIP_FILE, ZipFileAdapter)

__all__ = [
    "SkillAdapter",
    "ImportSourceType",
    "NormalizedSkill",
    "SkillAsset",
    "SkillCommand",
    "SkillImportError",
    "AdapterRegistry",
    "get_adapter",
    "SkillRepoAdapter",
    "ClaudeMarketAdapter",
    "ZipFileAdapter",
]
```

## Usage Examples

### Import from Claude Marketplace

```python
from skills.import_service import UnifiedImportService
from skills.adapters.base import ImportSourceType

service = UnifiedImportService(session)

# Import from Claude marketplace
skill = await service.import_skill(
    source="https://github.com/nicobailon/visual-explainer",
    user_id=current_user.user_id,
    source_type=ImportSourceType.CLAUDE_MARKET
)
```

### Auto-detect Source Type

```python
# Auto-detect adapter
skill = await service.import_skill(
    source="https://example.com/agentskills-index.json",
    user_id=current_user.user_id
    # Adapter will be auto-detected as SKILL_REPO
)
```

### Preview Before Import

```python
# Preview skill metadata
preview = await service.preview_skill(
    source="https://github.com/nicobailon/visual-explainer",
    source_type=ImportSourceType.CLAUDE_MARKET
)

print(preview)
# {
#     "name": "visual-explainer",
#     "description": "Generate beautiful HTML pages...",
#     "version": "0.6.3",
#     "command_count": 8
# }
```

### Browse Repository

```python
# List available skills in repository
skills = await service.list_available_skills(
    source="https://github.com/blitz/skills-repo",
    source_type=ImportSourceType.SKILL_REPO
)

for skill in skills:
    print(f"- {skill['name']}: {skill['description']}")
```

## Creating Custom Adapters

To add support for a new skill source:

```python
from skills.adapters.base import SkillAdapter, ImportSourceType, NormalizedSkill
from skills.adapters.registry import AdapterRegistry

class MyCustomAdapter(SkillAdapter):
    @property
    def source_type(self) -> ImportSourceType:
        return ImportSourceType.MY_CUSTOM_SOURCE
    
    async def can_handle(self, source: str, **kwargs) -> bool:
        # Check if source matches your format
        return source.startswith("https://mysource.com/")
    
    async def validate_source(self, source: str, **kwargs) -> dict:
        # Return metadata preview
        return {"name": "...", "description": "..."}
    
    async def fetch_and_normalize(self, source: str, **kwargs) -> NormalizedSkill:
        # Fetch and convert to NormalizedSkill
        return NormalizedSkill(...)
    
    async def get_skill_list(self, source: str, **kwargs) -> list:
        # List available skills
        return [...]

# Register adapter
AdapterRegistry.register(ImportSourceType.MY_CUSTOM_SOURCE, MyCustomAdapter)
```

## Benefits

1. **Single API**: One import interface for all sources
2. **Extensible**: Add new adapters without changing core code
3. **Testable**: Each adapter is independently testable
4. **Auto-detection**: Automatically detects source type
5. **Preview support**: Preview skills before importing
6. **Unified security**: All imports go through same security scanner

## Migration Path

1. Create adapter framework (base classes, registry)
2. Implement adapters for existing sources
3. Refactor existing code to use adapters
4. Add new adapters (Claude marketplace, etc.)
5. Deprecate old hardcoded import paths
