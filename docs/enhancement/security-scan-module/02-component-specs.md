# Security Scan Module - Component Specifications

> **Document Type:** Technical Component Specs  
> **Status:** Draft  
> **Last Updated:** 2026-03-11

---

## 1. MCP Server Component

### 1.1 Overview

The MCP Server is the entry point for all security scanning operations. It exposes tools via the MCP JSON-RPC protocol over HTTP+SSE.

**File:** `infra/security-scanner/main.py`

**Responsibilities:**
- Handle incoming MCP requests
- Route requests to appropriate scanners
- Format responses according to MCP spec
- Handle errors gracefully
- Provide health check endpoints

### 1.2 Interface

```python
@app.post("/sse")
async def handle_mcp(request: Request) -> JSONResponse:
    """
    Handle MCP JSON-RPC requests.
    
    Supports:
    - tools/list: List available security scanning tools
    - tools/call: Execute a specific scanning tool
    
    Returns:
        JSON-RPC 2.0 compliant response
    """
```

### 1.3 Tool Registry

```python
TOOLS = [
    {
        "name": "scan_dependencies",
        "description": "Scan Python dependencies for known vulnerabilities using pip-audit",
        "inputSchema": {
            "type": "object",
            "properties": {
                "requirements_txt": {
                    "type": "string",
                    "description": "Content of requirements.txt file"
                },
                "pyproject_toml": {
                    "type": "string", 
                    "description": "Content of pyproject.toml file"
                },
                "severity_threshold": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "default": "medium",
                    "description": "Minimum severity level to report"
                }
            }
        }
    },
    {
        "name": "scan_secrets",
        "description": "Scan code for secrets, tokens, and credentials",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_code": {
                    "type": "string",
                    "description": "Source code to scan"
                },
                "file_path": {
                    "type": "string",
                    "description": "Path for context",
                    "default": "unknown"
                },
                "scan_type": {
                    "type": "string",
                    "enum": ["quick", "deep"],
                    "default": "quick",
                    "description": "Scan thoroughness"
                }
            },
            "required": ["source_code"]
        }
    },
    {
        "name": "scan_code",
        "description": "Static code analysis with bandit and semgrep",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_code": {
                    "type": "string",
                    "description": "Source code to analyze"
                },
                "language": {
                    "type": "string",
                    "enum": ["python", "javascript", "typescript"],
                    "default": "python",
                    "description": "Programming language"
                },
                "rule_set": {
                    "type": "string",
                    "enum": ["default", "strict", "owasp"],
                    "default": "default",
                    "description": "Rule set to apply"
                }
            },
            "required": ["source_code"]
        }
    },
    {
        "name": "validate_policy",
        "description": "Validate resource against security policy",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_type": {
                    "type": "string",
                    "enum": ["skill", "workflow", "configuration"],
                    "description": "Type of resource"
                },
                "resource_data": {
                    "type": "object",
                    "description": "Resource data to validate"
                },
                "policy_id": {
                    "type": "string",
                    "description": "Specific policy to apply (optional)"
                }
            },
            "required": ["resource_type", "resource_data"]
        }
    },
    {
        "name": "get_scan_history",
        "description": "Get scan history for a resource",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_id": {
                    "type": "string",
                    "description": "Resource identifier"
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "Maximum results to return"
                }
            },
            "required": ["resource_id"]
        }
    }
]
```

### 1.4 Error Handling

```python
# Standard MCP error codes
ERROR_CODES = {
    -32601: "Method not found",
    -32602: "Invalid params",
    -32603: "Internal error",
    -32000: "Scan timeout",
    -32001: "Scanner unavailable",
    -32002: "Invalid policy",
    -32003: "Database error"
}

# Error response format
{
    "jsonrpc": "2.0",
    "id": request_id,
    "error": {
        "code": -32603,
        "message": "Internal error: scanner timeout",
        "data": {
            "tool": "scan_dependencies",
            "timeout_seconds": 300
        }
    }
}
```

### 1.5 Health Endpoints

```python
@app.get("/health")
async def health_check() -> dict:
    """
    Liveness probe for Kubernetes.
    
    Returns:
        {"status": "healthy", "version": "1.0.0"}
    """

@app.get("/ready")
async def readiness_check() -> dict:
    """
    Readiness probe for Kubernetes.
    
    Checks:
    - Database connectivity
    - Vulnerability database freshness
    - Scanner availability
    
    Returns:
        {
            "status": "ready",
            "checks": {
                "database": "ok",
                "vuln_db": "ok",
                "scanners": "ok"
            }
        }
    """
```

---

## 2. Dependency Scanner Component

### 2.1 Overview

Scans Python dependencies for known vulnerabilities using pip-audit against the OSV (Open Source Vulnerabilities) database.

**File:** `infra/security-scanner/scanners/dependency_scanner.py`

**External Tool:** pip-audit

### 2.2 Class Definition

```python
class DependencyScanner:
    """
    Scans Python dependencies for known vulnerabilities.
    
    Usage:
        scanner = DependencyScanner()
        result = await scanner.scan(
            requirements_txt="requests==2.30.0",
            severity_threshold="medium"
        )
    """
    
    async def scan(
        self,
        requirements_txt: Optional[str] = None,
        pyproject_toml: Optional[str] = None,
        severity_threshold: str = "medium"
    ) -> dict[str, Any]:
        """
        Scan dependencies for vulnerabilities.
        
        Args:
            requirements_txt: Content of requirements.txt
            pyproject_toml: Content of pyproject.toml
            severity_threshold: Minimum severity (low/medium/high/critical)
            
        Returns:
            Scan result dictionary with:
            - status: "passed" | "failed" | "error"
            - scanned_at: ISO timestamp
            - vulnerabilities: List of vulnerability objects
            - total_packages: Number of packages scanned
            - vulnerable_packages: Number with vulnerabilities
            - summary: Human-readable summary
        """
```

### 2.3 Data Models

```python
@dataclass
class Vulnerability:
    """Single vulnerability finding."""
    package: str              # Package name
    version: str              # Affected version
    vuln_id: str              # PYSEC-* or CVE-*
    description: str          # Vulnerability description
    severity: str             # critical, high, medium, low
    fix_version: Optional[str]  # Version that fixes it
    aliases: list[str]        # CVE IDs, etc.

@dataclass
class DependencyScanResult:
    """Result of dependency scan."""
    status: str               # passed, failed, error
    scanned_at: str           # ISO timestamp
    vulnerabilities: list[Vulnerability]
    total_packages: int
    vulnerable_packages: int
    summary: str
```

### 2.4 Severity Levels

| Level | CVSS Range | Description |
|-------|------------|-------------|
| critical | 9.0-10.0 | Immediate action required |
| high | 7.0-8.9 | Fix as soon as possible |
| medium | 4.0-6.9 | Fix in next release |
| low | 0.1-3.9 | Fix when convenient |

### 2.5 Implementation Notes

1. **Caching:** Cache pip-audit results for 1 hour to avoid repeated OSV queries
2. **Timeout:** Enforce 120-second timeout per scan
3. **Temp Files:** Create temporary files for requirements.txt/pyproject.toml
4. **Error Handling:** Return "error" status on pip-audit failure, not exception

---

## 3. Secret Scanner Component

### 3.1 Overview

Detects secrets, credentials, and sensitive data in source code using detect-secrets.

**File:** `infra/security-scanner/scanners/secret_scanner.py`

**External Tool:** detect-secrets

### 3.2 Class Definition

```python
class SecretScanner:
    """
    Scans code for secrets and credentials.
    
    Usage:
        scanner = SecretScanner()
        result = await scanner.scan(
            source_code="API_KEY = 'sk-1234567890'",
            scan_type="quick"
        )
    """
    
    async def scan(
        self,
        source_code: str,
        file_path: str = "unknown",
        scan_type: str = "quick"
    ) -> dict[str, Any]:
        """
        Scan code for secrets.
        
        Args:
            source_code: Source code to scan
            file_path: Path for context (used in reporting)
            scan_type: "quick" or "deep" (deep uses more plugins)
            
        Returns:
            Scan result with:
            - status: "passed" | "failed" | "error"
            - scanned_at: ISO timestamp
            - findings: List of secret findings
            - total_issues: Total secrets found
            - summary: Human-readable summary
        """
```

### 3.3 Data Models

```python
@dataclass
class SecretFinding:
    """Single secret detection."""
    type: str                 # Secret type (API Key, Password, etc.)
    severity: str             # critical, high, medium, low
    location: str             # file:line reference
    line: str                 # Line content (sanitized)
    line_number: int          # Line number
    hashed_secret: str        # SHA256 hash of secret
    plugin: str               # Which detector found it

@dataclass
class SecretScanResult:
    """Result of secret scan."""
    status: str
    scanned_at: str
    findings: list[SecretFinding]
    total_issues: int
    summary: str
```

### 3.4 Secret Types Detected

| Type | Examples | Severity |
|------|----------|----------|
| API Keys | `sk-`, `api_key=` | critical |
| Passwords | `password=`, `passwd:` | critical |
| Tokens | `token=`, `bearer ` | critical |
| Private Keys | `BEGIN RSA PRIVATE KEY` | critical |
| AWS Keys | `AKIA...` | critical |
| Database URLs | `postgresql://user:pass@` | high |
| JWT Tokens | `eyJhbG...` | high |

### 3.5 Privacy Considerations

```python
def _hash_secret(secret: str) -> str:
    """
    Hash secret for storage/presentation.
    Never store or log actual secrets.
    """
    import hashlib
    return hashlib.sha256(secret.encode()).hexdigest()[:16]

def _sanitize_line(line: str, secret: str) -> str:
    """
    Replace secret with placeholder in line display.
    """
    return line.replace(secret, "***REDACTED***")
```

---

## 4. Code Scanner Component

### 4.1 Overview

Performs static code analysis using bandit to find security issues in Python code.

**File:** `infra/security-scanner/scanners/code_scanner.py`

**External Tool:** bandit

### 4.2 Class Definition

```python
class CodeScanner:
    """
    Static code analysis for security issues.
    
    Usage:
        scanner = CodeScanner()
        result = await scanner.scan(
            source_code="eval(user_input)",
            rule_set="default"
        )
    """
    
    async def scan(
        self,
        source_code: str,
        language: str = "python",
        rule_set: str = "default"
    ) -> dict[str, Any]:
        """
        Scan code for security issues.
        
        Args:
            source_code: Source code to analyze
            language: Programming language (currently only "python")
            rule_set: "default", "strict", or "owasp"
            
        Returns:
            Scan result with:
            - status: "passed" | "failed" | "error"
            - scanned_at: ISO timestamp
            - findings: List of security findings
            - total_issues: Total issues found
            - summary: Human-readable summary
        """
```

### 4.3 Rule Sets

**Default:**
- SQL injection (B608)
- Command injection (B605, B607)
- Hardcoded passwords (B105, B106, B107)
- Unsafe eval/exec (B307, B102)
- Weak cryptography (B303, B304)

**Strict:** (Default + additional)
- All assert statements (B101)
- Try/except/pass (B110)
- YAML load (B506)
- Markup safe (B703)

**OWASP:**
- Focus on OWASP Top 10
- Injection flaws
- Broken authentication
- Sensitive data exposure
- XML external entities
- Broken access control

### 4.4 Data Models

```python
@dataclass
class CodeFinding:
    """Single code security issue."""
    type: str                 # "security"
    severity: str             # critical, high, medium, low
    rule_id: str              # Bandit test ID (e.g., "B605")
    tool: str                 # "bandit"
    message: str              # Human-readable description
    location: str             # file:line
    line_number: int
    cwe: Optional[str]        # CWE identifier
    confidence: str           # high, medium, low

@dataclass
class CodeScanResult:
    """Result of code scan."""
    status: str
    scanned_at: str
    findings: list[CodeFinding]
    total_issues: int
    metrics: dict             # Lines of code, etc.
    summary: str
```

### 4.5 Severity Mapping

| Bandit Severity | Our Severity |
|----------------|--------------|
| HIGH | high |
| MEDIUM | medium |
| LOW | low |

| Bandit Confidence | Action |
|-------------------|--------|
| HIGH | Always report |
| MEDIUM | Report if severity >= medium |
| LOW | Report only in strict mode |

---

## 5. Policy Engine Component

### 5.1 Overview

Validates resources against configurable security policies.

**File:** `infra/security-scanner/scanners/policy_scanner.py`

### 5.2 Class Definition

```python
class PolicyScanner:
    """
    Validates resources against security policies.
    
    Usage:
        scanner = PolicyScanner()
        result = await scanner.validate(
            resource_type="skill",
            resource_data=skill_data,
            policy_id="skill-sandbox-restriction"
        )
    """
    
    def __init__(self):
        self.policies: dict[str, Policy] = {}
        self._load_policies()
    
    async def validate(
        self,
        resource_type: str,
        resource_data: dict[str, Any],
        policy_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Validate resource against policy.
        
        Args:
            resource_type: Type of resource (skill, workflow, configuration)
            resource_data: Resource data to validate
            policy_id: Specific policy to use (or default for type)
            
        Returns:
            Validation result with:
            - status: "passed" | "failed"
            - policy_id: Policy used
            - violations: List of policy violations
            - summary: Human-readable summary
        """
    
    def _load_policies(self) -> None:
        """Load policies from YAML files."""
        
    async def reload_policies(self) -> None:
        """Hot-reload policies without restart."""
```

### 5.3 Policy Data Model

```python
@dataclass
class PolicyRule:
    """Single policy rule."""
    rule_id: str
    name: str
    rule_type: str              # threshold, regex, blocklist, custom
    severity: str               # error, warning, info
    config: dict[str, Any]      # Rule-specific configuration
    message: str                # Violation message
    autofix: Optional[dict]     # Auto-fix configuration

@dataclass
class Policy:
    """Security policy definition."""
    policy_id: str
    name: str
    policy_type: str            # dependency, secret, code, custom
    description: str
    version: str
    applies_to: list[dict]      # Resource type conditions
    rules: list[PolicyRule]
    is_active: bool
    is_default: bool

@dataclass
class PolicyViolation:
    """Single policy violation."""
    rule_id: str
    severity: str
    message: str
    matched_data: dict          # What triggered the violation
    remediation: Optional[str]  # How to fix
```

### 5.4 Rule Types

**Threshold Rule:**
```yaml
rule:
  type: threshold
  config:
    metric: "critical_vulnerabilities"  # What to measure
    max_value: 0                         # Maximum allowed
    min_value: null                      # Optional minimum
```

**Blocklist Rule:**
```yaml
rule:
  type: blocklist
  config:
    field: "tools"                       # Field to check
    blocked_items: ["admin.*", "system.*"]  # Patterns to block
    match_type: "glob"                   # glob, regex, exact
```

**Regex Rule:**
```yaml
rule:
  type: regex
  config:
    field: "source_code"
    pattern: "eval\s*\("
    flags: "i"                           # Case insensitive
```

**Custom Rule:**
```yaml
rule:
  type: custom
  config:
    condition: "tool_matches"
    pattern: "sandbox.*"
    required_field: "sandbox_enabled"
    required_value: true
```

### 5.5 Hot Reload

```python
import asyncio
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class PolicyReloadHandler(FileSystemEventHandler):
    """Watch for policy file changes."""
    
    def __init__(self, scanner: PolicyScanner):
        self.scanner = scanner
        self._reload_task: Optional[asyncio.Task] = None
    
    def on_modified(self, event):
        if event.src_path.endswith('.yaml'):
            # Debounce reloads
            if self._reload_task:
                self._reload_task.cancel()
            self._reload_task = asyncio.create_task(
                self._debounced_reload()
            )
    
    async def _debounced_reload(self):
        await asyncio.sleep(1)  # Wait 1s after last change
        await self.scanner.reload_policies()

# Start watching
observer = Observer()
handler = PolicyReloadHandler(scanner)
observer.schedule(handler, path='policies/', recursive=True)
observer.start()
```

---

## 6. Backend Client Component

### 6.1 Overview

Python client for AgentOS backend to communicate with Security Scanner service.

**File:** `backend/mcp/security_scan_client.py`

### 6.2 Class Definition

```python
class SecurityScanClient:
    """
    Client for security scanner MCP server.
    
    Usage:
        client = SecurityScanClient("http://security-scanner:8003")
        result = await client.scan_dependencies(
            requirements_txt=requirements_content
        )
    """
    
    def __init__(self, server_url: str = "http://security-scanner:8003"):
        self._client = MCPClient(server_url)
        self._logger = structlog.get_logger(__name__)
    
    async def scan_dependencies(
        self,
        requirements_txt: Optional[str] = None,
        pyproject_toml: Optional[str] = None,
        severity_threshold: str = "medium"
    ) -> dict[str, Any]:
        """Scan Python dependencies."""
    
    async def scan_secrets(
        self,
        source_code: str,
        file_path: str = "unknown",
        scan_type: str = "quick"
    ) -> dict[str, Any]:
        """Scan code for secrets."""
    
    async def scan_code(
        self,
        source_code: str,
        language: str = "python",
        rule_set: str = "default"
    ) -> dict[str, Any]:
        """Run static code analysis."""
    
    async def validate_policy(
        self,
        resource_type: str,
        resource_data: dict,
        policy_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Validate against security policy."""
    
    async def get_scan_history(
        self,
        resource_id: str,
        limit: int = 10
    ) -> list[dict]:
        """Get scan history for resource."""
```

### 6.3 Error Handling

```python
class SecurityScanError(Exception):
    """Base exception for security scan errors."""
    pass

class SecurityScanTimeoutError(SecurityScanError):
    """Scan exceeded timeout."""
    pass

class SecurityScanUnavailableError(SecurityScanError):
    """Scanner service unavailable."""
    pass

class SecurityViolation(Exception):
    """Resource violated security policy."""
    def __init__(self, violations: list[dict]):
        self.violations = violations
        super().__init__(f"Security violations: {len(violations)}")
```

### 6.4 Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=lambda e: isinstance(e, SecurityScanUnavailableError)
)
async def _call_with_retry(self, tool_name: str, arguments: dict) -> dict:
    """Call scanner with retry logic."""
    result = await self._client.call_tool(tool_name, arguments)
    if not result.get("success"):
        error = result.get("error", {})
        if error.get("code") == -32001:
            raise SecurityScanUnavailableError("Scanner unavailable")
        raise SecurityScanError(error.get("message", "Unknown error"))
    return result
```

---

## 7. Database Repository Component

### 7.1 Overview

Data access layer for scan results and policies.

**File:** `infra/security-scanner/database/repository.py`

### 7.2 Repository Class

```python
class ScanRepository:
    """Repository for scan results."""
    
    def __init__(self, session: AsyncSession):
        self._session = session
    
    async def save_scan_result(
        self,
        resource_id: str,
        resource_type: str,
        scan_type: str,
        status: str,
        findings: list[dict],
        summary: str,
        score: Optional[int] = None,
        scanner_version: Optional[str] = None,
        policy_id: Optional[str] = None
    ) -> SecScanResult:
        """Save scan result to database."""
    
    async def get_scan_history(
        self,
        resource_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> list[SecScanResult]:
        """Get scan history for resource."""
    
    async def get_latest_scan(
        self,
        resource_id: str,
        scan_type: Optional[str] = None
    ) -> Optional[SecScanResult]:
        """Get most recent scan for resource."""
    
    async def delete_old_scans(
        self,
        retention_days: int = 90
    ) -> int:
        """Delete scans older than retention period."""


class PolicyRepository:
    """Repository for security policies."""
    
    def __init__(self, session: AsyncSession):
        self._session = session
    
    async def get_policy(self, policy_id: str) -> Optional[SecScanPolicy]:
        """Get policy by ID."""
    
    async def get_default_policy(
        self,
        resource_type: str
    ) -> Optional[SecScanPolicy]:
        """Get default policy for resource type."""
    
    async def list_policies(
        self,
        active_only: bool = True
    ) -> list[SecScanPolicy]:
        """List all policies."""
    
    async def save_policy(self, policy: SecScanPolicy) -> SecScanPolicy:
        """Save or update policy."""
    
    async def delete_policy(self, policy_id: str) -> bool:
        """Delete policy."""
```

---

## 8. API Routes Component

### 8.1 Overview

REST API endpoints for AgentOS backend.

**File:** `backend/api/routes/security_scan.py`

### 8.2 Route Definitions

```python
router = APIRouter(prefix="/security", tags=["security"])

@router.post("/scan", response_model=ScanResultResponse)
async def trigger_scan(
    request: ScanRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["security:scan"])),
):
    """Trigger a security scan."""

@router.get("/history/{resource_id}", response_model=ScanHistoryResponse)
async def get_scan_history(
    resource_id: str,
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get scan history for resource."""

@router.get("/policies", response_model=PolicyListResponse)
async def list_policies(
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["security:admin"])),
):
    """List security policies."""

@router.post("/policies", response_model=PolicyResponse)
async def create_policy(
    policy: PolicyCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["security:admin"])),
):
    """Create new security policy."""

@router.get("/policies/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["security:admin"])),
):
    """Get policy by ID."""

@router.put("/policies/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: str,
    policy: PolicyUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["security:admin"])),
):
    """Update security policy."""

@router.delete("/policies/{policy_id}")
async def delete_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["security:admin"])),
):
    """Delete security policy."""

@router.get("/sbom/{resource_id}")
async def get_sbom(
    resource_id: str,
    format: str = Query("spdx-json", enum=["spdx-json", "cyclonedx-json"]),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get SBOM for resource."""
```

---

## 9. Configuration Component

### 9.1 Configuration Model

```python
class ScannerConfig(BaseSettings):
    """Configuration for security scanner service."""
    
    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    
    # Scanning
    scan_timeout: int = Field(300, env="SCAN_TIMEOUT")
    max_scan_concurrency: int = Field(5, env="MAX_SCAN_CONCURRENCY")
    
    # Updates
    vuln_db_update_interval: int = Field(86400, env="VULN_DB_UPDATE_INTERVAL")
    policy_update_interval: int = Field(3600, env="POLICY_UPDATE_INTERVAL")
    
    # Retention
    result_retention_days: int = Field(90, env="RESULT_RETENTION_DAYS")
    
    # Logging
    log_level: str = Field("info", env="LOG_LEVEL")
    
    # Policies
    policies_directory: str = Field("/app/policies", env="POLICIES_DIRECTORY")
    
    class Config:
        env_file = ".env"
```

### 9.2 Default Configuration

```yaml
# config.yaml
defaults:
  # Scanning behavior
  scanning:
    default_severity_threshold: "medium"
    fail_on_error: true
    cache_results: true
    cache_ttl_seconds: 3600
  
  # Policy evaluation
  policies:
    default_policy: "default"
    strict_mode: false
    auto_reload: true
  
  # Notifications
  notifications:
    on_critical: true
    on_high: true
    on_medium: false
    channels: ["webhook", "log"]
  
  # Performance
  performance:
    max_concurrent_scans: 5
    scan_timeout_seconds: 300
    memory_limit_mb: 512
```

---

## 10. Component Interaction Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                         User Request                            │
└──────────────────────┬─────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────────────┐
│                    AgentOS Backend                              │
│  ┌──────────────────────────────────────────────────────┐      │
│  │           SecurityScanClient                          │      │
│  │  - Validates permissions                              │      │
│  - Formats request                                      │      │
│  │  - Handles retries                                    │      │
│  │  - Processes response                                 │      │
│  └────────────────────┬─────────────────────────────────┘      │
└───────────────────────┼────────────────────────────────────────┘
                        │ HTTP+SSE
                        ▼
┌────────────────────────────────────────────────────────────────┐
│                    MCP Server (main.py)                         │
│  ┌──────────────────────────────────────────────────────┐      │
│  │              Request Router                           │      │
│  │  ┌──────────┬──────────┬──────────┬──────────┐       │      │
│  │  │scan_deps │scan_secrets│scan_code │validate │       │      │
│  │  └────┬─────┴────┬─────┴────┬─────┴────┬─────┘       │      │
│  └───────┼──────────┼──────────┼──────────┼─────────────┘      │
└──────────┼──────────┼──────────┼──────────┼────────────────────┘
           │          │          │          │
           ▼          ▼          ▼          ▼
┌────────────────────────────────────────────────────────────────┐
│                        Scanners                                 │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ Dependency   │ │ Secret       │ │ Code         │            │
│  │ Scanner      │ │ Scanner      │ │ Scanner      │            │
│  │ (pip-audit)  │ │(detect-secrets)│ │ (bandit)    │            │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘            │
│         │                │                │                    │
│         └────────────────┴────────────────┘                    │
│                          │                                     │
└──────────────────────────┼─────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│                      Policy Engine                              │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  - Loads policies from YAML                           │      │
│  │  - Evaluates rules                                    │      │
│  │  - Aggregates violations                              │      │
│  │  - Generates recommendations                          │      │
│  └────────────────────┬─────────────────────────────────┘      │
└───────────────────────┼────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────┐
│                    Database Layer                               │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  - Saves scan results                                 │      │
│  │  - Retrieves history                                  │      │
│  │  - Manages policies                                   │      │
│  │  - Enforces retention                                 │      │
│  └──────────────────────────────────────────────────────┘      │
└────────────────────────────────────────────────────────────────┘
```

---

*Document Version: 1.0*  
*Last Updated: 2026-03-11*
