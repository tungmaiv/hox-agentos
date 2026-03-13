# CLI-Anything Integration Design Document

**Status:** Draft  
**Created:** 2026-03-12  
**Author:** AgentOS Architecture Team  

---

## Executive Summary

This document proposes the integration of [CLI-Anything](https://github.com/HKUDS/CLI-Anything) into Blitz AgentOS as a complementary tool execution layer alongside the existing MCP infrastructure. CLI-Anything transforms any software with a codebase into agent-native CLI tools through an automated 7-phase pipeline, offering significant advantages over traditional MCP servers for internal applications.

### Key Benefits

- **275x token efficiency**: ~200 tokens per CLI task vs 55,000 tokens for MCP tool dumping
- **Universal compatibility**: Works with any software that has a codebase or API documentation
- **Self-describing**: Built-in `--help` and `--json` flags for automatic discovery
- **Deterministic**: Unix pipes reliability with structured JSON output
- **Real backends**: Calls actual applications (GIMP, Blender, LibreOffice) not toy implementations

### Strategic Decision

Adopt a **dual-stack architecture** that maintains existing MCP infrastructure for public/community tools while adding CLI-Anything support for internal/custom integrations. Both systems route through AgentOS's unified 3-gate security engine.

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            AGENTOS TOOL RUNTIME                              │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                    UNIFIED SECURITY ENGINE (3-Gate)                      │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────────┐  │ │
│  │  │  Gate 1     │  │  Gate 2     │  │  Gate 3                         │  │ │
│  │  │  JWT        │→ │  RBAC       │→ │  Tool ACL                       │  │ │
│  │  │  Validation │  │  Check      │  │  (per-user, per-tool)           │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────────────┐
│    MCP Mode          │  │  CLI-Anything        │  │   CLI-Anything               │
│    (Existing)        │  │  Sandbox Mode        │  │   Adapter Mode               │
│                      │  │  (Primary)           │  │   (Future Enhancement)       │
├──────────────────────┤  ├──────────────────────┤  ├──────────────────────────────┤
│ • HTTP+SSE transport │  │ • CLI runs in        │  │ • Long-lived subprocess      │
│ • Public MCP servers │  │   sandbox container  │  │ • Connection reuse           │
│ • Community tools    │  │ • One-shot execution │  │ • Better for interactive     │
│ • Stateful sessions  │  │ • Fresh container    │  │   workflows                  │
│                      │  │   per call           │  │ • Process pooling            │
└──────────────────────┘  └──────────────────────┘  └──────────────────────────────┘
```

### Design Principles

1. **Unified Security**: All tools (MCP, CLI-Anything, Backend) pass through identical 3-gate security
2. **Existing Infrastructure Reuse**: Leverage current sandbox executor, registry, and credential systems
3. **Incremental Adoption**: Start with sandbox mode, add adapter mode later if needed
4. **Backward Compatibility**: No changes to existing MCP or backend tool implementations
5. **Single Source of Truth**: Registry remains in `registry_entries` table with type-specific handlers

---

## Implementation Modes

### Mode 1: CLI-Anything Sandbox Mode (Primary)

**Execution Model:**
- CLI-Anything generates Python CLI packages (e.g., `cli-anything-jira`)
- AgentOS executes them via existing `SandboxExecutor`
- Each tool invocation spins up a fresh Docker container
- Container auto-destroyed after execution

**Registry Configuration:**

```json
{
  "name": "jira-create-issue",
  "type": "tool",
  "handler_type": "cli_anything",
  "config": {
    "cli_package": "cli-anything-jira",
    "cli_command": "cli-anything-jira issue create",
    "install_script": "pip install cli-anything-jira",
    "json_output": true,
    "requires_auth": true,
    "auth_env_vars": ["JIRA_TOKEN", "JIRA_BASE_URL"],
    "timeout_seconds": 30,
    "resource_profile": "standard"
  },
  "input_schema": {
    "type": "object",
    "properties": {
      "project_key": {"type": "string"},
      "summary": {"type": "string"},
      "description": {"type": "string"},
      "issue_type": {"type": "string", "enum": ["Bug", "Task", "Story"]}
    },
    "required": ["project_key", "summary"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "issue_key": {"type": "string"},
      "url": {"type": "string"},
      "status": {"type": "string"}
    }
  }
}
```

**Execution Flow:**

```python
async def execute_cli_anything_tool(
    tool_config: dict,
    user_context: UserContext,
    arguments: dict
) -> dict:
    """Execute CLI-Anything tool in sandbox."""
    
    # 1. Security gates (already passed before this point)
    # Gate 1: JWT validation
    # Gate 2: RBAC permission check
    # Gate 3: Tool ACL check
    
    # 2. Retrieve credentials from secure store
    credentials = await credential_store.get(
        user_id=user_context.user_id,
        service=tool_config["cli_package"]
    )
    
    # 3. Build environment variables (never in command line)
    env_vars = {
        "CLI_ANYTHING_JSON": "1",  # Force JSON output
    }
    for env_var in tool_config["auth_env_vars"]:
        env_vars[env_var] = credentials.get_token(env_var)
    
    # 4. Build CLI command with JSON arguments
    args_json = json.dumps(arguments)
    code = f"""
import subprocess
import json
import sys

args = json.loads('{args_json}')
arg_list = []
for key, value in args.items():
    arg_list.extend([f'--{{key}}', str(value)])

result = subprocess.run(
    ['{tool_config["cli_command"]}', '--json'] + arg_list,
    capture_output=True,
    text=True
)
print(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
"""
    
    # 5. Execute in sandbox with resource limits
    result = await sandbox_executor.execute(
        code=code,
        language="python",
        timeout=tool_config.get("timeout_seconds", 30),
        env=env_vars
    )
    
    # 6. Parse JSON output
    if result.exit_code == 0:
        return json.loads(result.stdout)
    else:
        raise ToolExecutionError(result.stderr)
```

**Pros:**
- ✅ Uses existing sandbox infrastructure (no new security code)
- ✅ Maximum isolation (fresh container per call)
- ✅ Simple mental model: CLI = sandbox tool
- ✅ No process management complexity
- ✅ Consistent with current sandbox tool implementation

**Cons:**
- ❌ Higher latency (~1-2s container startup)
- ❌ No connection reuse for session-based APIs
- ❌ Higher resource usage per call

**Best For:**
- Stateless operations (create issue, fetch data)
- Infrequent tool usage
- High-security requirements
- Initial rollout and testing

---

### Mode 2: CLI-Anything Adapter Mode (Future)

**Execution Model:**
- Run CLI in persistent subprocess with REPL mode
- Maintain long-lived connection for multiple calls
- Connection pooling for popular tools
- Health checks and automatic restart

**Architecture:**

```python
# backend/tools/cli_anything_adapter.py
class CLIAnythingAdapter:
    """
    Long-lived adapter for CLI-Anything tools.
    Maintains persistent subprocess with REPL interface.
    """
    
    def __init__(self, cli_command: str, pool_size: int = 3):
        self.cli_command = cli_command
        self.pool = ConnectionPool(pool_size)
        self.health_checker = HealthChecker()
    
    async def call(self, command: str, args: dict) -> dict:
        """
        Send command to REPL, receive JSON response.
        Uses connection pooling for concurrent requests.
        """
        conn = await self.pool.acquire()
        try:
            # Send command as JSON line
            request = {"command": command, "args": args}
            conn.stdin.write(json.dumps(request) + "\n")
            await conn.stdin.drain()
            
            # Read JSON response
            response_line = await conn.stdout.readline()
            return json.loads(response_line)
        finally:
            await self.pool.release(conn)
    
    async def health_check(self) -> bool:
        """Verify REPL is responsive."""
        try:
            result = await asyncio.wait_for(
                self.call("ping", {}),
                timeout=5.0
            )
            return result.get("status") == "ok"
        except Exception:
            return False
```

**Pros:**
- ✅ Lower latency (~50-100ms warm calls)
- ✅ Connection reuse for session-based APIs
- ✅ Better for interactive workflows
- ✅ Supports stateful operations

**Cons:**
- ❌ More complex (process management, health checks, pooling)
- ❌ Less isolation than sandbox mode
- ❌ Requires careful resource management
- ❌ Needs development effort

**Best For:**
- High-frequency tool usage
- Session-based APIs (streaming, notifications)
- Interactive agent workflows
- Production optimization after sandbox mode validation

---

## Discovery & Registration

### Auto-Discovery Service

Implement a `CLIAnythingDiscoveryService` that automatically discovers and registers CLI-Anything tools:

```python
# backend/registry/cli_anything_discovery.py
class CLIAnythingDiscoveryService:
    """
    Discovers CLI-Anything packages and registers them as AgentOS tools.
    """
    
    CURATED_PACKAGES = [
        "cli-anything-jira",
        "cli-anything-confluence",
        "cli-anything-github",
        "cli-anything-gitlab",
        "cli-anything-slack",
        "cli-anything-notion",
        "cli-anything-linear",
        "cli-anything-asana",
        "cli-anything-trello",
    ]
    
    async def discover_package(self, package_name: str) -> list[dict]:
        """
        Install CLI package in temporary sandbox and extract schema.
        
        Steps:
        1. Install package: pip install {package_name}
        2. Run: {cli_command} --help --json
        3. Parse command structure and arguments
        4. Generate registry entries for each subcommand
        """
        
    async def auto_install_curated(self) -> int:
        """
        Install and register all curated CLI-Anything packages.
        Returns number of tools registered.
        """
        
    async def register_from_github_repo(self, repo_url: str) -> list[dict]:
        """
        Build CLI from GitHub repo using CLI-Anything methodology,
        then register the resulting package.
        """
```

### Registration Flow

```
User/Admin Initiates Discovery
        │
        ▼
DiscoveryService validates package exists
        │
        ▼
Install in temporary sandbox container
        │
        ▼
Extract schema via --help --json
        │
        ▼
Generate registry_entries for each command
        │
        ▼
Set handler_type='cli_anything'
        │
        ▼
Store in database
        │
        ▼
Tool available to agents
```

### Manual Registration API

For custom/internal CLI packages:

```python
POST /api/registry/cli-anything/discover
{
  "package_name": "cli-anything-custom-crm",
  "source": "pypi",  # or "github", "local"
  "auto_enable": true,
  "credential_mappings": {
    "CRM_API_TOKEN": "api_token",
    "CRM_BASE_URL": "base_url"
  }
}

Response:
{
  "tools_registered": 5,
  "tools": [
    {"name": "crm-contact-list", "description": "..."},
    {"name": "crm-contact-create", "description": "..."},
    ...
  ]
}
```

---

## Security Model

### Unified 3-Gate Security

All CLI-Anything tools pass through the same security infrastructure as MCP and backend tools:

```
┌────────────────────────────────────────────────────────────────┐
│                        GATE 1: JWT VALIDATION                   │
├────────────────────────────────────────────────────────────────┤
│ • Verify JWT signature against Keycloak public key             │
│ • Check token expiration                                       │
│ • Validate issuer and audience                                 │
│ • Extract user_id, roles from claims                           │
│                                                                 │
│ Output: Authenticated UserContext (user_id, roles, permissions)│
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                        GATE 2: RBAC CHECK                       │
├────────────────────────────────────────────────────────────────┤
│ • Map Keycloak roles to AgentOS permissions                   │
│ • Check if user has 'tool:use' permission                      │
│ • Verify specific tool category permissions                    │
│   (e.g., 'tool:use:cli-anything', 'tool:use:sandbox')         │
│                                                                 │
│ Output: Authorized UserContext with permission set             │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                        GATE 3: TOOL ACL                         │
├────────────────────────────────────────────────────────────────┤
│ • Query ToolAcl table for (user_id, tool_name)                │
│ • If explicit deny → 403 Forbidden                             │
│ • If explicit allow → Proceed                                  │
│ • If no entry → Default allow (enterprise: default deny)      │
│                                                                 │
│ Output: ACL decision (allow/deny)                              │
└────────────────────────────────────────────────────────────────┘
```

### Credential Management

CLI-Anything tools require API credentials. AgentOS provides secure credential storage:

```python
# backend/security/credentials.py
class CredentialStore:
    """
    Secure storage for API credentials.
    Credentials encrypted at rest (AES-256).
    """
    
    async def store(
        self,
        user_id: UUID,
        service: str,  # e.g., "cli-anything-jira"
        credentials: dict
    ) -> None:
        """Store encrypted credentials for user."""
        
    async def get(
        self,
        user_id: UUID,
        service: str
    ) -> dict:
        """Retrieve and decrypt credentials."""
```

**Credential Injection:**
- Never pass credentials in CLI arguments (visible in process list)
- Always inject via environment variables
- Environment variables isolated to sandbox container
- Credentials masked in audit logs

### Audit Logging

All CLI-Anything executions are audited:

```python
audit_logger.info(
    "cli_anything_tool_call",
    user_id=str(user_id),
    tool_name=tool_name,
    cli_command=cli_command,
    allowed=True,
    duration_ms=duration,
    exit_code=result.exit_code,
    # NEVER log: credentials, full output (may contain sensitive data)
)
```

---

## Integration with Existing Systems

### Registry Integration

Extend existing registry handlers:

```python
# backend/registry/handlers/cli_anything_handler.py
class CLIAnythingHandler(RegistryHandler):
    """Handler for CLI-Anything tool entries."""
    
    def validate_config(self, config: dict) -> None:
        """Validate CLI-Anything specific configuration."""
        required = ["cli_package", "cli_command"]
        for field in required:
            if not config.get(field):
                raise ValueError(f"CLI-Anything config missing '{field}'")
        
        # Validate auth_env_vars if requires_auth
        if config.get("requires_auth") and not config.get("auth_env_vars"):
            raise ValueError("Authenticated CLI tool must specify auth_env_vars")
    
    async def on_create(self, entry: RegistryEntry, session: AsyncSession) -> None:
        """Ensure CLI package is installed."""
        # Trigger async installation in background
        await cli_package_manager.ensure_installed(entry.config["cli_package"])
```

### Sandbox Integration

Reuse existing `SandboxExecutor`:

```python
# backend/sandbox/cli_anything_executor.py
class CLIAnythingSandboxExecutor:
    """
    Specialized executor for CLI-Anything tools.
    Wraps base SandboxExecutor with CLI-specific logic.
    """
    
    def __init__(self):
        self.sandbox = SandboxExecutor()
    
    async def execute(
        self,
        cli_command: str,
        arguments: dict,
        credentials: dict,
        timeout: int = 30
    ) -> dict:
        # Build wrapper code
        # Inject credentials as env vars
        # Execute in sandbox
        # Parse JSON output
        pass
```

### Skill Executor Integration

CLI-Anything tools work seamlessly with procedural skills:

```python
# In SkillExecutor, tool step handling:
if tool.handler_type == "cli_anything":
    result = await cli_anything_executor.execute(
        cli_command=tool.config["cli_command"],
        arguments=step.arguments,
        credentials=await credential_store.get(user_id, tool.config["cli_package"]),
        timeout=tool.config.get("timeout_seconds", 30)
    )
```

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

**Goal:** Basic sandbox mode support

**Tasks:**
1. Create `CLIAnythingHandler` in registry handlers
2. Implement `CLIAnythingSandboxExecutor`
3. Add credential store integration
4. Create manual registration API endpoint
5. Add audit logging

**Deliverables:**
- Can manually register CLI-Anything tools
- Can execute CLI tools through sandbox
- Security gates functional
- Basic tests passing

### Phase 2: Auto-Discovery (Weeks 3-4)

**Goal:** Automated package discovery and registration

**Tasks:**
1. Implement `CLIAnythingDiscoveryService`
2. Create package installation pipeline
3. Build schema extraction from `--help --json`
4. Add curated package list
5. Create admin UI for discovery

**Deliverables:**
- Auto-discovery endpoint working
- Curated packages auto-installable
- Schema extraction accurate
- Documentation complete

### Phase 3: Integration & Polish (Weeks 5-6)

**Goal:** Production-ready integration

**Tasks:**
1. Error handling and retry logic
2. Performance monitoring
3. Resource usage optimization
4. Comprehensive test suite
5. User documentation

**Deliverables:**
- Production-ready CLI-Anything support
- Full test coverage
- Documentation complete
- Performance benchmarks

### Phase 4: Adapter Mode (Future)

**Goal:** Long-lived process support for performance

**Pre-requisites:**
- Phase 1-3 proven in production
- Performance bottlenecks identified
- Resource requirements justified

**Tasks:**
1. Design connection pooling
2. Implement health checking
3. Add process lifecycle management
4. Build migration path from sandbox mode

---

## Comparison: MCP vs CLI-Anything

| Aspect | MCP | CLI-Anything Sandbox | CLI-Anything Adapter |
|--------|-----|---------------------|---------------------|
| **Latency** | Low (HTTP) | High (~1-2s) | Low (~50-100ms) |
| **Isolation** | Process-level | Container-level | Process-level |
| **State** | Stateful sessions | Stateless | Stateful sessions |
| **Token Usage** | High (55k tokens) | Low (~200 tokens) | Low (~200 tokens) |
| **Setup Complexity** | Medium (MCP server) | Low (pip install) | Low (pip install) |
| **Best For** | Public tools, complex workflows | Internal APIs, security-critical | High-frequency usage |
| **Discovery** | tools/list endpoint | --help --json | --help --json |
| **Community** | Growing ecosystem | Emerging (11 tools proven) | Emerging |

---

## Open Questions & Decisions

### 1. Package Management

**Question:** Where do CLI-Anything packages come from?

**Options:**
- A. PyPI only (standard Python packages)
- B. GitHub repos (build on-demand with CLI-Anything methodology)
- C. Internal registry (private packages)
- D. All of the above

**Recommendation:** Start with A (PyPI), add B (GitHub) for custom builds.

### 2. Naming Convention

**Question:** How should CLI-Anything tools be named in the registry?

**Options:**
- A. Keep CLI-Anything prefix: `cli-anything-jira-create-issue`
- B. Simplify: `jira-create-issue`
- C. Namespace: `cli/jira-create-issue`

**Recommendation:** Option B with metadata indicating source.

### 3. Default Security Stance

**Question:** Default allow or default deny for CLI-Anything tools?

**Options:**
- A. Default allow (like current ToolAcl)
- B. Default deny (explicit allowlist required)
- C. Per-environment configuration

**Recommendation:** Option C - default allow in dev, default deny in production.

### 4. Adapter Mode Priority

**Question:** Should we implement adapter mode now or wait?

**Options:**
- A. Build both modes now (more upfront work, complete solution)
- B. Sandbox mode only (validate usage patterns first)
- C. Adapter mode only (if performance is critical)

**Recommendation:** Option B - prove sandbox mode, add adapter when needed.

---

## Appendix

### A. CLI-Anything Package Format

Standard CLI-Anything packages follow this structure:

```
cli-anything-<software>/
├── cli_anything/
│   ├── <software>/
│   │   ├── __init__.py
│   │   ├── cli.py          # Click CLI definition
│   │   ├── core.py         # Core functionality
│   │   ├── backend.py      # Backend wrapper
│   │   └── tests/
│   └── shared/
│       └── repl_skin.py    # Unified REPL interface
├── setup.py
└── README.md
```

### B. Example: JIRA CLI-Anything Integration

**Installation:**
```bash
pip install cli-anything-jira
```

**Manual Usage:**
```bash
# Set credentials
export JIRA_TOKEN="your-token"
export JIRA_BASE_URL="https://your-instance.atlassian.net"

# List issues
cli-anything-jira issue list --project PROJ --json

# Create issue
cli-anything-jira issue create --project PROJ --summary "Bug" --type Bug --json
```

**AgentOS Integration:**
```python
# Registered as tool: jira-issue-create
# Agent calls via natural language:
# "Create a bug in project PROJ about login failure"

result = await tool_registry.call_tool(
    name="jira-issue-create",
    user_id=user_id,
    arguments={
        "project": "PROJ",
        "summary": "Login failure",
        "type": "Bug",
        "description": "Users cannot log in..."
    }
)
```

### C. Migration Path

For existing MCP servers that could be replaced by CLI-Anything:

1. **Assessment:** Evaluate if CLI-Anything version exists or can be built
2. **Parallel Run:** Deploy both, compare functionality
3. **Gradual Cutover:** Route traffic percentage to CLI-Anything
4. **Deprecation:** Mark MCP version deprecated
5. **Removal:** Remove MCP server after validation period

---

## References

1. [CLI-Anything GitHub Repository](https://github.com/HKUDS/CLI-Anything)
2. [AgentOS Unified Registry Proposal](./unified-registry-proposal.md)
3. [AgentOS MCP Enhancement Proposal](./mcp-server-enhancement-proposal.md)
4. [AgentOS Security Architecture](../architecture/security.md)

---

## Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-03-12 | Initial draft |
