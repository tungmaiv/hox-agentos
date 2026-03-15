# Universal Skill Import System - Design Document

**Topic:** #5 GitHub Repository Skill Sources (Extended to Universal Import)  
**Status:** ✅ Design Complete - Ready for Implementation Planning  
**Date:** 2026-03-14  
**Related Topics:** #8 (Analytics Dashboard), #11 (Mission Control)

---

## Executive Summary

AgentOS v1.4 introduces a **Universal Skill Import System** with an extensible adapter pattern that enables importing skills from multiple external sources. The system treats GitHub as the primary source (supporting both single-skill repos and `skills/` folder structures) with ZIP file upload as a fallback for offline/air-gapped environments.

**Key Features:**
- **Adapter Pattern**: Clean separation allowing future sources (GitLab, Bitbucket, Gitea)
- **Skill-Tool Bundling**: Skills can include private tools that run in mandatory sandboxes
- **References & Output Formats**: Skills can declare documentation references and structured output schemas
- **Security-First**: All imports undergo security scanning; private tools enforce sandbox isolation
- **Observability**: Full integration with Dashboard (#8) and Mission Control (#11)

**Scope:**
- **v1.4 (Current):** GitHub public repos, ZIP files, agentskills-index.json
- **v1.5 (Future):** GitLab, Bitbucket, Gitea, private repos, GitHub App
- **v1.6 (Future):** Full plugin ecosystem with dependency resolution

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SKILL IMPORT ORCHESTRATOR                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────────┐   │
│  │   GitHub     │  │    ZIP       │  │    Index JSON                    │   │
│  │   Adapter    │  │   Adapter    │  │    Adapter                       │   │
│  └──────────────┘  └──────────────┘  └──────────────────────────────────┘   │
│         │                 │                    │                            │
│         └─────────────────┴────────────────────┘                            │
│                           │                                                 │
│                ┌──────────▼──────────┐                                      │
│                │  RawSkillBundle     │                                      │
│                │  ┌───────────────┐  │                                      │
│                │  │ SKILL.md      │  │                                      │
│                │  │ metadata.json │  │                                      │
│                │  │ /tools/       │  │  ← Tool definitions (private)        │
│                │  │ /references/  │  │  ← External references               │
│                │  │ /schemas/     │  │  ← Output format schemas             │
│                │  └───────────────┘  │                                      │
│                └──────────┬──────────┘                                      │
│                           │                                                 │
│  ┌────────────────────────┼────────────────────────┐                       │
│  ▼                        ▼                        ▼                       │
│ ┌────────┐          ┌──────────┐          ┌───────────────┐               │
│ │Security│          │  Parser  │          │  Sandbox      │               │
│ │Scanner │          │ (multi-  │          │  Validator    │               │
│ │        │          │  format) │          │  (tools only) │               │
│ └────────┘          └──────────┘          └───────────────┘               │
│      │                   │                      │                          │
│      └───────────────────┴──────────────────────┘                          │
│                          │                                                 │
│               ┌──────────▼──────────┐                                      │
│               │   Import Decision   │                                      │
│               │  (immediate/delayed)│                                      │
│               └──────────┬──────────┘                                      │
│                          │                                                 │
│    ┌─────────────────────┼─────────────────────┐                          │
│    ▼                     ▼                     ▼                          │
│ ┌──────────┐    ┌──────────────┐    ┌──────────────┐                     │
│ │SkillDef  │    │ ToolDef      │    │ SkillRef     │                     │
│ │(output   │    │ (private,    │    │ (references) │                     │
│ │ format)  │    │  sandbox)    │    │              │                     │
│ └──────────┘    └──────────────┘    └──────────────┘                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Adapter Pattern**: Each source implements `BaseSkillAdapter` interface
2. **Normalization Pipeline**: All sources converge to `RawSkillBundle` → `SkillDefinition`
3. **Security-First**: Security scan BEFORE parsing; private tools require sandbox
4. **Configurable Import Flow**: Per-repository policies (immediate vs approval)
5. **Extensibility**: New adapters without core code changes

---

## Core Components

### 1. BaseSkillAdapter (Abstract Interface)

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class DiscoveryResult:
    """Result from discovering skills in a source"""
    skill_count: int
    source_metadata: dict[str, Any]  # TODO: use TypedDict for complex structures in implementation
    skills: list[dict[str, Any]]  # Minimal metadata for listing

@dataclass
class FetchResult:
    """Result from fetching a specific skill"""
    success: bool
    bundle: Optional[RawSkillBundle]
    error: Optional[str]

class BaseSkillAdapter(ABC):
    """Abstract base for all skill source adapters"""
    
    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return adapter type: 'github', 'zip', 'index_json', etc."""
        pass
    
    @abstractmethod
    async def validate_source(self, source_url: str) -> bool:
        """Validate that the source is accessible and valid"""
        pass
    
    @abstractmethod
    async def discover(self, source_url: str) -> DiscoveryResult:
        """Discover all available skills in the source"""
        pass
    
    @abstractmethod
    async def fetch(self, source_url: str, skill_id: str) -> FetchResult:
        """Fetch a specific skill and return RawSkillBundle"""
        pass
    
    @abstractmethod
    async def check_updates(self, source_url: str, skill_id: str, 
                           current_version: str) -> Optional[str]:
        """Check if update available, return new version or None"""
        pass
```

### 2. RawSkillBundle Structure

```python
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum

class ToolVisibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    PROTECTED = "protected"

class ToolType(str, Enum):
    MCP = "mcp"
    HTTP = "http"
    PYTHON = "python"
    JAVASCRIPT = "javascript"

@dataclass
class ToolBundle:
    """A tool bundled with a skill"""
    name: str
    visibility: ToolVisibility
    sandbox_required: bool  # ENFORCED: True for private tools
    tool_type: ToolType
    metadata: dict[str, Any]  # Parsed from tool.json; TODO: use TypedDict for complex structures in implementation
    handler_code: str  # Implementation code
    schema: dict[str, Any]  # Input/output schema
    parent_skill_id: Optional[str] = None

@dataclass
class SkillReference:
    """External reference attached to a skill"""
    ref_type: str  # documentation, api_reference, example, related_skill, etc.
    title: str
    url: Optional[str]
    content: Optional[str]
    metadata: Optional[dict]

@dataclass
class OutputFormat:
    """Output format specification for a skill"""
    format_type: str  # markdown, json_schema, xml, text, structured
    schema: Optional[dict]  # JSON Schema for validation
    template: Optional[str]  # Jinja2 template
    example: Optional[str]  # Example output

@dataclass
class SkillMetadata:
    """Core skill metadata"""
    name: str
    display_name: Optional[str]
    description: Optional[str]
    version: str
    skill_type: str  # instructional | procedural
    category: Optional[str]
    tags: List[str]
    author: Optional[str]
    license: Optional[str]
    compatibility: List[str]  # ['claude-code', 'cursor', 'opencode']
    slash_command: Optional[str]
    when_to_use: Optional[str]
    related_skills: List[str]

@dataclass
class RawSkillBundle:
    """Complete skill bundle from any source"""
    metadata: SkillMetadata
    instruction_markdown: str
    procedure_json: Optional[dict]  # For procedural skills
    tools: List[ToolBundle]  # 0..N bundled tools
    references: List[SkillReference]  # External references
    output_format: Optional[OutputFormat]  # Output specification
    source_url: str
    source_hash: str  # For caching/updates
    raw_files: dict[str, bytes]  # Additional asset files
```

### 3. Skill Import Orchestrator

```python
class SkillImportOrchestrator:
    """Central coordinator for skill imports from all sources"""
    
    def __init__(
        self,
        adapters: List[BaseSkillAdapter],
        security_scanner: SecurityScanner,
        normalizer: SkillNormalizer,
        repository: SkillRepository,
        decision_engine: ImportDecisionEngine
    ):
        self.adapters = {a.source_type: a for a in adapters}
        self.security_scanner = security_scanner
        self.normalizer = normalizer
        self.repository = repository
        self.decision_engine = decision_engine
    
    async def import_skill(
        self,
        source_url: str,
        skill_id: Optional[str] = None,
        import_policy: str = "default"  # default, immediate, approval
    ) -> ImportResult:
        """
        Main entry point for importing a skill
        
        Flow:
        1. Detect source type and get appropriate adapter
        2. Fetch RawSkillBundle from source
        3. Run security scan
        4. Parse and normalize to AgentOS format
        5. Validate sandbox requirements for private tools
        6. Apply import decision (immediate vs approval queue)
        7. Create SkillDefinition + ToolDefinitions + References
        """
        # 1. Detect adapter
        adapter = self._detect_adapter(source_url)
        
        # 2. Validate source
        if not await adapter.validate_source(source_url):
            return ImportResult(success=False, error="Invalid source")
        
        # 3. Fetch bundle
        fetch_result = await adapter.fetch(source_url, skill_id)
        if not fetch_result.success:
            return ImportResult(success=False, error=fetch_result.error)
        
        bundle = fetch_result.bundle
        
        # 4. Security scan
        scan_result = await self.security_scanner.scan(bundle)
        if scan_result.blocked:
            return ImportResult(
                success=False,
                error=f"Security scan failed: {scan_result.reason}",
                security_report=scan_result.report
            )
        
        # 5. Validate bundle structure
        validation = self._validate_bundle(bundle)
        if not validation.valid:
            return ImportResult(success=False, error=validation.errors)
        
        # 6. Normalize to AgentOS format
        normalized = self.normalizer.normalize(bundle)
        
        # 7. Check import decision
        decision = await self.decision_engine.decide(
            normalized, import_policy, scan_result
        )
        
        if decision.action == "queue_for_approval":
            queued_id = await self.repository.queue_for_approval(normalized)
            return ImportResult(
                success=True,
                status="pending_approval",
                queued_id=queued_id
            )
        
        # 8. Import immediately
        skill_def = await self.repository.create_skill(normalized)
        
        # 9. Import bundled tools
        for tool in normalized.tools:
            await self.repository.create_tool(tool, parent_skill=skill_def)
        
        # 10. Import references
        for ref in normalized.references:
            await self.repository.create_reference(ref, skill=skill_def)
        
        return ImportResult(
            success=True,
            status="imported",
            skill_id=skill_def.id,
            tools_imported=len(normalized.tools),
            security_score=scan_result.score
        )
    
    def _validate_bundle(self, bundle: RawSkillBundle) -> ValidationResult:
        """Validate bundle structure and enforce rules"""
        errors = []
        
        # ENFORCED: Private tools must require sandbox
        for tool in bundle.tools:
            if tool.visibility == ToolVisibility.PRIVATE:
                if not tool.sandbox_required:
                    errors.append(
                        f"Tool '{tool.name}': Private tools must have "
                        f"sandbox_required=true"
                    )
        
        # Validate output format schema
        if bundle.output_format and bundle.output_format.schema:
            if not self._validate_json_schema(bundle.output_format.schema):
                errors.append("Invalid output format JSON schema")
        
        return ValidationResult(valid=len(errors) == 0, errors=errors)
```

---

## Adapters

### GitHub Adapter

Supports two repository structures:

**Structure A: Single Skill per Repo**
```
repo/
├── SKILL.md              # Required: Skill instructions
├── metadata.json         # Required: Skill metadata
├── tools/                # Optional: Bundled tools
├── references/           # Optional: References
└── schemas/              # Optional: Output schemas
```

**Structure B: Skills Folder (Multiple Skills)**
```
repo/
├── skills/
│   ├── skill-a/
│   │   ├── SKILL.md
│   │   ├── metadata.json
│   │   └── tools/
│   └── skill-b/
│       ├── SKILL.md
│       └── metadata.json
└── index.json            # Optional: Skill index
```

```python
class GitHubAdapter(BaseSkillAdapter):
    """Adapter for importing skills from GitHub repositories"""
    
    @property
    def source_type(self) -> str:
        return "github"
    
    async def validate_source(self, source_url: str) -> bool:
        """Check if GitHub repo is accessible"""
        # Parse owner/repo from URL
        # Check repo exists and is public (or accessible with token)
        pass
    
    async def discover(self, source_url: str) -> DiscoveryResult:
        """Discover skills in GitHub repo"""
        # 1. Try to fetch index.json
        # 2. If no index, look for skills/ folder
        # 3. If no skills/, check for SKILL.md at root (single skill)
        pass
    
    async def fetch(self, source_url: str, skill_id: str) -> FetchResult:
        """Fetch skill from GitHub"""
        # 1. Determine skill path (root or skills/{skill_id}/)
        # 2. Fetch SKILL.md
        # 3. Fetch metadata.json
        # 4. Discover and fetch tools/
        # 5. Fetch references/
        # 6. Fetch schemas/
        # 7. Build RawSkillBundle
        pass
```

### ZIP Adapter

```python
class ZIPAdapter(BaseSkillAdapter):
    """Adapter for importing skills from ZIP files"""
    
    @property
    def source_type(self) -> str:
        return "zip"
    
    async def fetch_from_upload(
        self, 
        file_content: bytes,
        filename: str
    ) -> FetchResult:
        """Fetch skill from uploaded ZIP file"""
        # 1. Validate ZIP structure
        # 2. Extract files
        # 3. Parse same structure as GitHub adapter
        # 4. Build RawSkillBundle
        pass
```

### Index JSON Adapter

Supports existing `agentskills-index.json` protocol:

```python
class IndexJSONAdapter(BaseSkillAdapter):
    """Adapter for agentskills-index.json protocol"""
    
    @property
    def source_type(self) -> str:
        return "index_json"
    
    async def discover(self, source_url: str) -> DiscoveryResult:
        """Fetch and parse index.json"""
        # 1. Fetch index.json
        # 2. Parse skill list
        # 3. Return discovery result
        pass
```

---

## Security & Validation

### Security Scanner

```python
class SecurityScanner:
    """Scans skills for security issues before import"""
    
    async def scan(self, bundle: RawSkillBundle) -> SecurityScanResult:
        """Run security checks on skill bundle"""
        findings = []
        
        # 1. Secrets detection
        secrets = self._scan_for_secrets(bundle)
        findings.extend(secrets)
        
        # 2. Unsafe code patterns
        unsafe = self._scan_for_unsafe_patterns(bundle)
        findings.extend(unsafe)
        
        # 3. Dependency vulnerabilities
        deps = self._scan_dependencies(bundle)
        findings.extend(deps)
        
        # 4. Policy violations
        policy = self._check_policy_violations(bundle)
        findings.extend(policy)
        
        # Determine action
        critical = [f for f in findings if f.severity == "critical"]
        high = [f for f in findings if f.severity == "high"]
        
        blocked = len(critical) > 0
        flagged = len(high) > 0
        
        return SecurityScanResult(
            blocked=blocked,
            flagged=flagged,
            findings=findings,
            score=self._calculate_score(findings)
        )
    
    def _scan_for_secrets(self, bundle: RawSkillBundle) -> List[Finding]:
        """Scan for hardcoded secrets"""
        patterns = [
            (r'api[_-]?key["\']?\s*[:=]\s*["\']?[a-zA-Z0-9]{20,}', "API Key"),
            (r'password["\']?\s*[:=]\s*["\'][^"\']{8,}', "Password"),
            (r'secret["\']?\s*[:=]\s*["\'][^"\']{10,}', "Secret"),
            (r'private[_-]?key["\']?\s*[:=]', "Private Key"),
            (r'github[_-]?token["\']?\s*[:=]', "GitHub Token"),
        ]
        # Scan all files
        pass
    
    def _scan_for_unsafe_patterns(self, bundle: RawSkillBundle) -> List[Finding]:
        """Scan for unsafe code patterns"""
        patterns = [
            (r'eval\s*\(', "eval() usage"),
            (r'exec\s*\(', "exec() usage"),
            (r'subprocess\.call.*shell\s*=\s*True', "Shell=True"),
            (r'__import__\s*\(', "Dynamic import"),
            (r'pickle\.loads', "Unsafe deserialization"),
        ]
        pass
```

### Sandbox Enforcement

All private tools **MUST** run in sandbox:

```python
class ToolExecutor:
    """Executes tools with proper isolation"""
    
    async def execute(
        self, 
        tool: ToolDefinition, 
        context: ExecutionContext
    ) -> ExecutionResult:
        """Execute tool with appropriate isolation"""
        
        if tool.visibility == "private":
            # FORCE sandbox - no exceptions
            return await self.sandbox_executor.run(
                tool=tool,
                context=context,
                isolation_level="strict",
                resource_limits={
                    "cpu_ms": 5000,
                    "memory_mb": 128,
                    "timeout_seconds": 30
                }
            )
        else:
            # Public tools can run in-process or sandbox
            return await self.standard_executor.run(tool, context)
```

---

## Database Schema Extensions

### ToolDefinition Updates

```python
class ToolDefinition(Base):
    """Existing model with new fields for skill bundling"""
    
    # ... existing fields ...
    
    # NEW: Tool visibility
    visibility: Mapped[str] = mapped_column(
        String(20), 
        nullable=False, 
        server_default=text("'public'")
    )  # public | private | protected
    
    # NEW: Parent skill reference (for private tools)
    parent_skill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), 
        nullable=True,
        index=True
    )
    
    # NEW: Sandbox requirement (enforced for private tools)
    sandbox_required: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        server_default=text("false")
    )
    
    # NEW: Bundled from source tracking
    bundled_from_source: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )  # URL of source repo
    bundled_from_version: Mapped[str | None] = mapped_column(
        String(32), 
        nullable=True
    )
```

### New: SkillReference Model

```python
class SkillReference(Base):
    """External references attached to skills"""
    __tablename__ = "skill_references"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        nullable=False,
        index=True
    )
    
    ref_type: Mapped[str] = mapped_column(
        String(32), 
        nullable=False
    )  # documentation, api_reference, example, related_skill, source_code, tutorial, paper
    
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata: Mapped[dict | None] = mapped_column(_JSONB, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
```

### New: SkillOutputFormat Model

```python
class SkillOutputFormat(Base):
    """Output format specifications for skills"""
    __tablename__ = "skill_output_formats"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        nullable=False,
        index=True
    )
    
    format_type: Mapped[str] = mapped_column(
        String(32), 
        nullable=False
    )  # markdown, json_schema, xml, text, structured
    
    schema: Mapped[dict | None] = mapped_column(_JSONB, nullable=True)
    template: Mapped[str | None] = mapped_column(Text, nullable=True)
    example: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_rules: Mapped[dict | None] = mapped_column(_JSONB, nullable=True)
```

### New: SkillImportQueue Model

```python
class SkillImportQueue(Base):
    """Queue for skills pending approval"""
    __tablename__ = "skill_import_queue"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    skill_name: Mapped[str] = mapped_column(Text, nullable=False)
    
    raw_bundle: Mapped[dict] = mapped_column(_JSONB, nullable=False)
    security_report: Mapped[dict | None] = mapped_column(_JSONB, nullable=True)
    
    status: Mapped[str] = mapped_column(
        String(20), 
        nullable=False,
        server_default=text("'pending'")
    )  # pending, approved, rejected, imported
    
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), 
        nullable=True
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), 
        nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), 
        nullable=True
    )
```

---

## API Endpoints

### Admin Import Management

```python
# List import queue (pending approvals)
GET /api/admin/skills/import-queue
→ {
    "items": [
        {
            "id": "uuid",
            "skill_name": "email-processor",
            "source_url": "https://github.com/...",
            "source_type": "github",
            "status": "pending",
            "security_score": 95,
            "requested_at": "2026-03-14T08:30:00Z"
        }
    ]
}

# Approve/reject import
POST /api/admin/skills/import-queue/{id}/approve
POST /api/admin/skills/import-queue/{id}/reject

# Import skill from URL (admin only)
POST /api/admin/skills/import
{
    "source_url": "https://github.com/user/skill-repo",
    "import_policy": "immediate"  # or "approval"
}

# Upload ZIP file
POST /api/admin/skills/import-zip
Content-Type: multipart/form-data
→ Imported skill details
```

### Public Discovery (for Skill Catalog)

```python
# Discover skills in a repository
GET /api/skills/discover?source_url=https://github.com/user/repo
→ {
    "source_type": "github",
    "skill_count": 5,
    "skills": [
        {
            "name": "email-processor",
            "description": "Process incoming emails",
            "version": "1.0.0"
        }
    ]
}

# Preview skill before import
GET /api/skills/preview?source_url=...&skill_name=email-processor
→ RawSkillBundle preview (sanitized)
```

---

## UI Integration

### Admin Console - Skill Import Page

**Features:**
1. **Import from GitHub**
   - URL input with validation
   - Auto-discovery of available skills
   - Preview before import
   - Security scan results display

2. **Import from ZIP**
   - Drag-and-drop file upload
   - Structure validation
   - Preview and edit metadata

3. **Import Queue**
   - List pending approvals
   - Approve/reject actions
   - Security report viewer

4. **Repository Management**
   - Add/remove skill repositories
   - Configure import policies per repo
   - Auto-sync settings

### Mission Control Integration

**New Widgets:**
- **Skill Import Queue**: Shows pending imports, recent completions
- **Sandbox Execution Dashboard**: Active sandboxes, tool execution metrics
- **Tool Usage Analytics**: Most used private tools, success rates

### Analytics Dashboard Integration

**New Metrics:**
- Skill import volume and success rates
- Security scan statistics
- Sandbox resource usage
- Tool execution performance

---

## Observability

### Metrics

```python
# Skill Import Metrics
SKILL_IMPORT_TOTAL = Counter(
    "skill_import_total",
    "Total skill imports",
    ["source", "status"]
)

SKILL_IMPORT_DURATION = Histogram(
    "skill_import_duration_seconds",
    "Time spent importing skills",
    ["source"]
)

SKILL_SECURITY_SCAN_RESULT = Counter(
    "skill_security_scan_result",
    "Security scan results",
    ["result"]
)

# Sandbox Metrics
SANDBOX_EXECUTION_TOTAL = Counter(
    "sandbox_execution_total",
    "Total sandbox executions",
    ["tool_name", "status"]
)

SANDBOX_EXECUTION_DURATION = Histogram(
    "sandbox_execution_duration_seconds",
    "Tool execution time in sandbox",
    ["tool_name"]
)

SANDBOX_RESOURCE_USAGE = Gauge(
    "sandbox_resource_usage",
    "Resource usage per sandbox",
    ["resource_type"]
)

# Tool Metrics
TOOL_EXECUTION_TOTAL = Counter(
    "tool_execution_total",
    "Total tool executions",
    ["tool_name", "skill_name", "visibility", "status"]
)

PRIVATE_TOOL_ISOLATION_VIOLATIONS = Counter(
    "private_tool_isolation_violations",
    "Attempts to access private tools from unauthorized skills"
)
```

### Logging

```json
{
  "event": "skill_imported",
  "skill_id": "uuid",
  "skill_name": "email-processor",
  "source": "github",
  "source_url": "https://github.com/...",
  "import_duration_ms": 45000,
  "tools_imported": 2,
  "security_scan": "passed",
  "timestamp": "2026-03-14T08:30:00Z"
}

{
  "event": "sandbox_execution",
  "tool_id": "uuid",
  "tool_name": "send-email",
  "skill_id": "uuid",
  "skill_name": "email-processor",
  "execution_time_ms": 245,
  "status": "success",
  "resource_usage": {
    "cpu_ms": 120,
    "memory_mb": 45,
    "network_bytes": 2048
  }
}
```

---

## Implementation Phases

### Phase 1: Core Infrastructure
- BaseSkillAdapter interface
- GitHubAdapter (single skill repos)
- SecurityScanner framework
- Database migrations

### Phase 2: Import Flow
- SkillImportOrchestrator
- Import decision engine
- Import queue management
- Admin API endpoints

### Phase 3: Tool Bundling
- ToolBundle support
- Sandbox enforcement
- ToolScopeResolver
- Private tool isolation

### Phase 4: Advanced Features
- ZIP adapter
- Skills/ folder structure support
- Index JSON adapter
- References and output formats

### Phase 5: UI Integration
- Admin Console import page
- Mission Control widgets
- Analytics dashboard integration

---

## Future Roadmap

### v1.5: Extended Sources
- GitLab adapter
- Bitbucket adapter
- Gitea adapter
- Private GitHub repos (PAT auth)
- GitHub App integration (webhook auto-sync)
- Monorepo support (multiple skills in one repo)
- Version pinning (tags/branches)

### v1.6: Plugin Ecosystem
- Full plugin system (commands + agents + skills)
- Plugin marketplace UI
- Auto-update mechanism
- Plugin dependency resolution
- Multi-runtime compatibility layer
- Plugin rating and reviews

---

## Security Considerations

1. **Private Tool Isolation**: Enforced sandbox execution, no exceptions
2. **Secret Detection**: Scan all files for hardcoded credentials
3. **Unsafe Pattern Detection**: Block eval(), exec(), shell=True
4. **Dependency Scanning**: Check for known vulnerabilities
5. **Approval Workflow**: Optional human review for sensitive operations
6. **Audit Logging**: All imports logged with full context
7. **Resource Limits**: Sandboxes have strict CPU/memory/time limits
8. **Network Isolation**: Sandboxes have restricted network access

---

## Success Criteria

1. Import skills from GitHub repos (single skill and skills/ folder)
2. Import skills from ZIP uploads
3. Support existing agentskills-index.json protocol
4. Private tools automatically run in sandbox
5. Security scanning blocks malicious skills
6. Import approval workflow functional
7. Full observability in Dashboard and Mission Control
8. Extensible adapter architecture ready for v1.5 sources

---

**Next Step:** Create implementation plan (PLAN.md) using `/gsd:plan-phase` command.
