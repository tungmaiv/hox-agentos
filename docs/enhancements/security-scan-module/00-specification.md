# Security Scan Module - Implementation Specification

> **Document Type:** Technical Specification (Consolidated — merged 02-component-specs, 03-integration-guide, 04-deployment-guide)
> **Status:** Draft
> **Target Version:** v1.4
> **Last Updated:** 2026-03-12

---

## 1. Executive Summary

This document provides the complete technical specification for implementing a **standalone, independently maintainable Security Scan Module** for Blitz AgentOS. The module operates as a separate Docker service following the MCP (Model Context Protocol) pattern established by existing CRM and Timelog servers.

### Key Objectives

- **Independence:** Separate release cycle, versioning, and maintenance from AgentOS core
- **Scalability:** Independent scaling based on scanning workload  
- **Technology Freedom:** Use best-of-breed security scanning tools
- **Zero Core Impact:** Updates don't require AgentOS restarts
- **Enterprise Security:** Comprehensive scanning for skills, workflows, and configurations

---

## 2. Architecture Overview

### 2.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AGENTOS CORE                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │   Backend    │  │   Tool       │  │   Workflow   │                   │
│  │   FastAPI    │──│   Registry   │──│   Engine     │                   │
│  └──────┬───────┘  └──────────────┘  └──────────────┘                   │
│         │                                                                │
│  ┌──────▼───────┐  HTTP+SSE (MCP Protocol)                             │
│  │ SecurityScan │────────────────────────────────────┐                  │
│  │   Client     │                                    │                  │
│  └──────────────┘                                    │                  │
└──────────────────────────────────────────────────────┼──────────────────┘
                                                       │
                                                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    SECURITY SCANNER SERVICE                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │   FastAPI    │  │  Dependency  │  │   Secret     │                   │
│  │   Server     │──│   Scanner    │  │   Scanner    │                   │
│  └──────┬───────┘  └──────────────┘  └──────────────┘                   │
│         │              ┌──────────────┐  ┌──────────────┐               │
│         └──────────────│  Policy      │──│   SAST       │               │
│                        │  Engine      │  │   Engine     │               │
│                        └──────────────┘  └──────────────┘               │
│                                                                           │
│  External Tools: safety, pip-audit, bandit, detect-secrets, trivy        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Interaction Flow

```
1. User Action
   ↓
2. AgentOS Backend (triggers scan via SecurityScanClient)
   ↓
3. HTTP+SSE Request to Security Scanner Service
   ↓
4. MCP Server routes to appropriate Scanner
   ↓
5. Scanner executes (pip-audit, bandit, etc.)
   ↓
6. Results stored in secscan_results table
   ↓
7. Response returned to AgentOS
   ↓
8. Action taken (allow/block/warn)
```

### 2.3 Security Gates Integration

```
Workflow Execution:
┌─────────┐    ┌─────────┐    ┌─────────────┐    ┌─────────┐
│  Start  │───→│  Node 1 │───→│ Security    │───→│ Node 2  │
└─────────┘    └─────────┘    │    Gate     │    └─────────┘
                              └─────────────┘          ↑
                                    │                  │
                                    ↓                  │
                              ┌─────────────┐          │
                              │   Block     │──────────┘
                              │   (if fail) │
                              └─────────────┘
```

---

## 3. Directory Structure

```
infra/security-scanner/                    # New top-level module
├── Dockerfile                             # Multi-stage build
├── pyproject.toml                        # Dependencies: fastapi, safety, bandit
├── alembic/                              # Independent migrations
│   ├── env.py
│   ├── ini
│   └── versions/
├── main.py                               # FastAPI + MCP JSON-RPC handler
├── config.py                             # Scanner configuration
├── scanners/                             # Scanner implementations
│   ├── __init__.py
│   ├── base.py                          # Abstract scanner interface
│   ├── dependency_scanner.py            # pip-audit, safety integration
│   ├── secret_scanner.py                # detect-secrets, trufflehog
│   ├── code_scanner.py                  # bandit, semgrep, ruff
│   ├── policy_scanner.py                # OPA/rego policies
│   └── container_scanner.py             # trivy (Phase 2)
├── policies/                             # YAML/JSON policy definitions
│   ├── default-policies.yaml            # Default org policies
│   ├── skill-policies.yaml              # Skill-specific rules
│   └── workflow-policies.yaml           # Workflow validation rules
├── database/                             # Database models and access
│   ├── models.py                        # SQLAlchemy models
│   └── repository.py                    # Data access layer
├── clients/                              # External service clients
│   ├── vulnerability_db.py              # CVE/OSV database client
│   └── license_db.py                    # License compliance (Phase 2)
├── tests/                                # Comprehensive test suite
│   ├── conftest.py
│   ├── test_dependency_scanner.py
│   ├── test_secret_scanner.py
│   ├── test_policy_engine.py
│   └── fixtures/                        # Test data
└── scripts/                              # Maintenance scripts
    ├── update_vuln_db.py                # Daily CVE updates
    └── health_check.py                  # Service health check

backend/mcp/                              # Backend integration
└── security_scan_client.py              # Client for scanner service

backend/api/routes/                       # API routes
└── security_scan.py                     # Security scan endpoints

frontend/src/components/security/         # Frontend components (Phase 2)
├── SecurityScanPanel.tsx
├── ScanResultsTable.tsx
└── PolicyEditor.tsx
```

---

## 4. Technology Stack

### 4.1 Core Service

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Web Framework | FastAPI | 0.115+ | HTTP API + MCP handling |
| Database | PostgreSQL | 16+ | Scan results storage |
| ORM | SQLAlchemy | 2.0+ | Database access |
| Logging | structlog | Latest | Structured logging |
| Config | pydantic-settings | Latest | Configuration management |

### 4.2 Scanning Tools

| Scanner | Tool | License | Purpose |
|---------|------|---------|---------|
| Dependencies | pip-audit | Apache 2.0 | Python package vulnerabilities |
| Secrets | detect-secrets | Apache 2.0 | Credential/token detection |
| Code (SAST) | bandit | Apache 2.0 | Python security linting |
| Container | trivy | Apache 2.0 | Docker image scanning |

### 4.3 Integration

| Component | Protocol | Port | Description |
|-----------|----------|------|-------------|
| MCP Server | HTTP+SSE | 8003 | JSON-RPC protocol |
| Health Check | HTTP | 8003/health | Kubernetes liveness probe |
| Database | PostgreSQL | 5432 | Shared with AgentOS |

---

## 5. Data Models

### 5.1 Scan Results

```python
class SecScanResult(Base):
    """Stores scan results for resources."""
    __tablename__ = "secscan_results"
    
    id: UUID                    # Primary key
    resource_id: str            # Skill ID, Workflow ID, etc.
    resource_type: str          # skill, workflow, configuration
    scan_type: str              # dependency, secret, code, policy
    status: str                 # passed, failed, error
    score: int                  # 0-100 score (optional)
    findings: JSONB             # Structured findings array
    summary: str                # Human-readable summary
    scanner_version: str        # Scanner version for traceability
    policy_id: str              # Applied policy (optional)
    created_at: datetime        # Scan timestamp
```

**Example findings structure:**
```json
{
  "findings": [
    {
      "type": "vulnerability",
      "severity": "high",
      "title": "CVE-2023-1234: requests package vulnerability",
      "description": "Requests before 2.31.0 vulnerable to...",
      "location": "requirements.txt:3",
      "fix_available": true,
      "fix_version": "2.31.0",
      "references": ["https://nvd.nist.gov/vuln/detail/CVE-2023-1234"]
    }
  ]
}
```

### 5.2 Security Policies

```python
class SecScanPolicy(Base):
    """Security policies configuration."""
    __tablename__ = "secscan_policies"
    
    id: UUID                    # Primary key
    name: str                   # Unique policy name
    policy_type: str            # dependency, secret, code, custom
    description: str            # Human-readable description
    rules: JSONB                # Policy rules definition
    is_active: bool             # Enable/disable flag
    is_default: bool            # Default policy flag
    created_at: datetime        # Creation timestamp
    updated_at: datetime        # Last update timestamp
```

**Example policy rules:**
```json
{
  "rules": [
    {
      "rule": "max_critical_vulns",
      "value": 0,
      "severity": "error",
      "message": "Critical vulnerabilities must be fixed before deployment"
    },
    {
      "rule": "blocked_packages",
      "value": ["pickle", "eval"],
      "severity": "error",
      "message": "Dangerous modules not allowed"
    }
  ]
}
```

### 5.3 Vulnerability Cache

```python
class SecScanVulnerability(Base):
    """Cache of known vulnerabilities for offline scanning."""
    __tablename__ = "secscan_vulnerabilities"
    
    id: UUID                    # Primary key
    vuln_id: str                # PYSEC-*, CVE-*
    package_name: str           # Affected package
    affected_versions: JSONB    # Version ranges
    fixed_versions: JSONB       # Fixed in versions
    severity: str               # critical, high, medium, low
    description: str            # Vulnerability description
    aliases: JSONB              # CVE IDs, etc.
    published_at: datetime      # Published date
    updated_in_db_at: datetime  # Cache update time
```

---

## 6. API Specification

### 6.1 MCP Tools Interface

All tools exposed via `POST /sse` with JSON-RPC 2.0 protocol.

#### Tool: `scan_dependencies`

Scan Python dependencies for known vulnerabilities.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "scan_dependencies",
    "arguments": {
      "requirements_txt": "requests==2.30.0\nurllib3==1.26.0",
      "pyproject_toml": null,
      "severity_threshold": "medium"
    }
  },
  "id": 1
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "status": "failed",
    "scanned_at": "2026-03-11T10:30:00Z",
    "vulnerabilities": [
      {
        "package": "urllib3",
        "version": "1.26.0",
        "vuln_id": "PYSEC-2023-192",
        "description": "urllib3 before 1.26.5 vulnerable to...",
        "severity": "high",
        "fix_version": "1.26.5",
        "aliases": ["CVE-2021-33503"]
      }
    ],
    "total_packages": 2,
    "vulnerable_packages": 1,
    "summary": "Found 1 vulnerabilities above medium threshold"
  }
}
```

#### Tool: `scan_secrets`

Detect secrets and credentials in source code.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "scan_secrets",
    "arguments": {
      "source_code": "API_KEY = 'sk-1234567890abcdef'",
      "file_path": "config.py",
      "scan_type": "deep"
    }
  },
  "id": 2
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "status": "failed",
    "scanned_at": "2026-03-11T10:30:00Z",
    "findings": [
      {
        "type": "secret",
        "severity": "critical",
        "secret_type": "API Key",
        "location": "config.py:1",
        "line": "API_KEY = 'sk-1234567890abcdef'",
        "hashed_secret": "abc123..."
      }
    ],
    "total_issues": 1,
    "summary": "Found 1 potential secrets"
  }
}
```

#### Tool: `scan_code`

Run static code analysis.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "scan_code",
    "arguments": {
      "source_code": "import os\nos.system(user_input)",
      "language": "python",
      "rule_set": "default"
    }
  },
  "id": 3
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "status": "failed",
    "scanned_at": "2026-03-11T10:30:00Z",
    "findings": [
      {
        "type": "security",
        "severity": "high",
        "rule_id": "B605",
        "tool": "bandit",
        "message": "Starting a process with a shell, possible injection",
        "location": "line 2",
        "cwe": "CWE-78"
      }
    ],
    "total_issues": 1,
    "summary": "Found 1 security issues"
  }
}
```

#### Tool: `validate_policy`

Validate resource against security policy.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "validate_policy",
    "arguments": {
      "resource_type": "skill",
      "resource_data": {
        "name": "test_skill",
        "tools": ["admin.delete_user", "email.send"]
      },
      "policy_id": "skill-sandbox-restriction"
    }
  },
  "id": 4
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "status": "failed",
    "policy_id": "skill-sandbox-restriction",
    "violations": [
      {
        "rule": "blocked_tools",
        "severity": "error",
        "message": "Admin tools not allowed in skills",
        "matched_tools": ["admin.delete_user"]
      }
    ],
    "summary": "Policy validation failed: 1 violation"
  }
}
```

### 6.2 REST API Endpoints

AgentOS backend exposes REST endpoints that wrap MCP calls.

#### POST `/api/security/scan`

Trigger a security scan on a resource.

**Request:**
```json
{
  "scan_type": "dependencies",
  "resource_type": "skill",
  "resource_id": "skill-123",
  "content": {
    "requirements_txt": "requests==2.30.0"
  },
  "severity_threshold": "medium"
}
```

**Response:**
```json
{
  "scan_id": "uuid",
  "status": "completed",
  "result": {
    "status": "passed",
    "vulnerabilities": [],
    "summary": "No vulnerabilities found"
  },
  "created_at": "2026-03-11T10:30:00Z"
}
```

#### GET `/api/security/history/{resource_id}`

Get scan history for a resource.

**Response:**
```json
{
  "resource_id": "skill-123",
  "total_scans": 15,
  "history": [
    {
      "scan_id": "uuid",
      "scan_type": "dependencies",
      "status": "passed",
      "score": 95,
      "created_at": "2026-03-11T10:30:00Z"
    }
  ]
}
```

#### GET `/api/security/policies`

List all security policies.

**Response:**
```json
{
  "policies": [
    {
      "id": "uuid",
      "name": "dependency-critical-only",
      "policy_type": "dependency",
      "is_active": true,
      "is_default": true
    }
  ]
}
```

---

## 7. Policy Engine Specification

### 7.1 Policy Schema

```yaml
# Policy file structure (YAML)
policy:
  id: "unique-policy-id"           # Unique identifier
  name: "Human Readable Name"      # Display name
  type: "dependency|secret|code|custom"  # Policy type
  description: "What this policy does"
  version: "1.0"
  
  # When this policy applies
  applies_to:
    - resource_type: "skill"
      conditions:
        - field: "tools"
          operator: "contains"
          value: "sandbox"
    - resource_type: "workflow"
  
  # Policy rules
  rules:
    - id: "rule-identifier"
      name: "Human readable rule name"
      type: "threshold|regex|blocklist|custom"
      severity: "error|warning|info"  # Action on violation
      
      # Rule configuration (type-specific)
      config:
        # For threshold rules
        max_value: 0
        metric: "critical_vulnerabilities"
        
        # For regex rules
        pattern: "regex-pattern"
        
        # For blocklist rules
        blocked_items: ["item1", "item2"]
      
      # Message shown on violation
      message: "What went wrong and how to fix"
      
      # Optional: auto-fix suggestion
      autofix:
        enabled: true
        suggestion: "pip install --upgrade package"
```

### 7.2 Default Policies

#### Policy: `dependency-critical-only`

```yaml
policy:
  id: "dependency-critical-only"
  name: "Block Critical Vulnerabilities"
  type: "dependency"
  description: "Fail on critical severity vulnerabilities"
  
  rules:
    - id: "no-critical-vulns"
      type: "threshold"
      severity: "error"
      config:
        max_value: 0
        metric: "critical_vulnerabilities"
      message: "Critical vulnerabilities must be fixed before deployment"
    
    - id: "limit-high-vulns"
      type: "threshold"
      severity: "warning"
      config:
        max_value: 5
        metric: "high_vulnerabilities"
      message: "High vulnerabilities should be addressed soon"
```

#### Policy: `no-hardcoded-secrets`

```yaml
policy:
  id: "no-hardcoded-secrets"
  name: "No Hardcoded Secrets"
  type: "secret"
  description: "Block any hardcoded credentials"
  
  rules:
    - id: "zero-secrets"
      type: "threshold"
      severity: "error"
      config:
        max_value: 0
        metric: "secrets_found"
      message: "Hardcoded secrets are not allowed"
```

#### Policy: `skill-sandbox-restriction`

```yaml
policy:
  id: "skill-sandbox-restriction"
  name: "Skill Sandbox Restrictions"
  type: "custom"
  description: "Restrict dangerous operations in skills"
  
  applies_to:
    - resource_type: "skill"
  
  rules:
    - id: "no-admin-tools"
      type: "blocklist"
      severity: "error"
      config:
        blocked_items: ["admin.*", "system.*", "config.*"]
        field: "tools"
      message: "Admin tools not allowed in user-created skills"
    
    - id: "sandbox-required"
      type: "custom"
      severity: "warning"
      config:
        condition: "tool_matches"
        pattern: "(sandbox|exec|eval).*"
        required_field: "sandbox_enabled"
        required_value: true
      message: "Dangerous tools must run in sandbox"
```

---

## 8. Integration Points

### 8.1 AgentOS Backend Integration

#### Tool Registration

```python
# In main.py lifespan() function

async def register_security_tools(session: AsyncSession):
    """Register security scanning tools on startup."""
    from gateway.tool_registry import register_tool
    
    tools = [
        {
            "name": "security.scan_dependencies",
            "description": "Scan Python dependencies for vulnerabilities",
            "required_permissions": ["security:scan"],
            "handler_type": "mcp",
            "mcp_server": "security-scanner",
            "mcp_tool": "scan_dependencies"
        },
        {
            "name": "security.scan_secrets",
            "description": "Scan code for secrets and credentials",
            "required_permissions": ["security:scan"],
            "handler_type": "mcp",
            "mcp_server": "security-scanner",
            "mcp_tool": "scan_secrets"
        },
        {
            "name": "security.scan_code",
            "description": "Run static code analysis",
            "required_permissions": ["security:scan"],
            "handler_type": "mcp",
            "mcp_server": "security-scanner",
            "mcp_tool": "scan_code"
        },
        {
            "name": "security.validate_policy",
            "description": "Validate resource against security policy",
            "required_permissions": ["security:admin"],
            "handler_type": "mcp",
            "mcp_server": "security-scanner",
            "mcp_tool": "validate_policy"
        }
    ]
    
    for tool in tools:
        await register_tool(session, **tool)
```

#### Workflow Security Gate

```python
# In workflow execution

async def execute_workflow_node(node: WorkflowNode, state: BlitzState):
    """Execute workflow node with security checks."""
    
    if node.type == "security_scan":
        # Run security scan
        client = SecurityScanClient()
        
        scan_result = await client.validate_policy(
            resource_type="workflow",
            resource_data=state.workflow_context,
            policy_id=node.data.get("policy_id")
        )
        
        if scan_result["status"] == "failed":
            if node.data.get("fail_on") == "error":
                raise SecurityViolation(scan_result["violations"])
            else:
                # Log warning but continue
                logger.warning("security_violation", violations=scan_result["violations"])
    
    # Continue with normal execution
    ...
```

### 8.2 Skill Import Integration

```python
# In skill import flow

async def import_skill(skill_data: dict, user_id: UUID):
    """Import skill with security scanning."""
    
    # Run security scan
    client = SecurityScanClient()
    
    # Scan dependencies
    if skill_data.get("dependencies"):
        dep_result = await client.scan_dependencies(
            requirements_txt=skill_data["dependencies"]
        )
        if dep_result["status"] == "failed":
            raise SkillImportError(f"Dependency vulnerabilities found: {dep_result['summary']}")
    
    # Scan for secrets in code
    for script in skill_data.get("scripts", []):
        secret_result = await client.scan_secrets(
            source_code=script["source"],
            file_path=script.get("filename", "unknown")
        )
        if secret_result["status"] == "failed"]:
            raise SkillImportError(f"Secrets detected in {script.get('filename')}")
    
    # Validate against policy
    policy_result = await client.validate_policy(
        resource_type="skill",
        resource_data=skill_data
    )
    
    # Store scan result
    await store_scan_result(skill_data["id"], policy_result)
    
    # Continue with import
    ...
```

---

## 9. Deployment Specification

### 9.1 Docker Configuration

**Dockerfile:**
```dockerfile
# Multi-stage build for security scanner
FROM python:3.12-slim as builder

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml .
RUN pip install --no-cache-dir \
    fastapi uvicorn sqlalchemy asyncpg structlog \
    pip-audit bandit detect-secrets safety

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN useradd -m -u 1000 scanner
WORKDIR /app
COPY --chown=scanner:scanner . .
USER scanner

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

EXPOSE 8003
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
```

**Docker Compose Service:**
```yaml
security-scanner:
  build: ./infra/security-scanner
  ports:
    - "8003:8003"
  environment:
    - DATABASE_URL=postgresql://blitz:${POSTGRES_PASSWORD}@postgres/blitz
    - VULN_DB_UPDATE_INTERVAL=86400
    - POLICY_UPDATE_INTERVAL=3600
    - SCAN_TIMEOUT=300
    - LOG_LEVEL=info
  volumes:
    - security_scanner_data:/app/data
    - ./infra/security-scanner/policies:/app/policies:ro
  depends_on:
    postgres:
      condition: service_healthy
  restart: unless-stopped
  networks:
    - blitz-net
  healthcheck:
    test: ["CMD-SHELL", "curl -f http://localhost:8003/health || exit 1"]
    interval: 30s
    timeout: 10s
    retries: 5
```

### 9.2 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | Required | PostgreSQL connection string |
| `VULN_DB_UPDATE_INTERVAL` | 86400 | Seconds between CVE DB updates |
| `POLICY_UPDATE_INTERVAL` | 3600 | Seconds between policy reloads |
| `SCAN_TIMEOUT` | 300 | Maximum scan duration in seconds |
| `LOG_LEVEL` | info | Logging level (debug, info, warning, error) |
| `MAX_SCAN_CONCURRENCY` | 5 | Concurrent scans allowed |
| `RESULT_RETENTION_DAYS` | 90 | Days to keep scan results |

### 9.3 Health Checks

**Liveness Probe:**
```bash
GET /health
Response: {"status": "healthy", "version": "1.0.0"}
```

**Readiness Probe:**
```bash
GET /ready
Response: {"status": "ready", "checks": {"database": "ok", "vuln_db": "ok"}}
```

**Metrics Endpoint:**
```bash
GET /metrics
Response: Prometheus format metrics
```

---

## 10. Security Considerations

### 10.1 Access Control

**Permissions Required:**
- `security:scan` - Run security scans
- `security:admin` - Manage policies, view all results
- `security:override` - Bypass security gates (emergency)

**Gate 3 ACL Integration:**
```sql
-- Tool ACL entries
INSERT INTO tool_acl (user_id, tool_name, allowed) VALUES
  ('admin-user-uuid', 'security.validate_policy', true),
  ('developer-user-uuid', 'security.scan_dependencies', true);
```

### 10.2 Data Protection

- Scan results contain no credentials (hashed secrets only)
- Database encrypted at rest (PostgreSQL TDE)
- TLS 1.3 for all service communication
- No scan data logged to external systems

### 10.3 Sandbox Requirements

The scanner service itself runs with:
- Non-root user (UID 1000)
- Read-only filesystem (except /app/data)
- No network access for scanning processes
- Resource limits (CPU: 1.0, Memory: 512MB)

---

## 11. Monitoring & Alerting

### 11.1 Key Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `security_scans_total` | Counter | Total scans run by type |
| `security_scan_duration_seconds` | Histogram | Scan duration |
| `security_vulnerabilities_found` | Counter | Vulns by severity |
| `security_scan_errors` | Counter | Failed scans |
| `security_policy_violations` | Counter | Policy violations |
| `secscanner_up` | Gauge | Service availability |

### 11.2 Alert Rules

**Critical:**
- Scanner service down > 5 minutes
- Database connection failures
- > 10 critical vulnerabilities in production

**Warning:**
- Scan queue backlog > 50
- Vulnerability DB > 24 hours old
- Policy update failures

**Info:**
- Daily scan summary
- New policy violations
- Scanner version updates available

---

## 12. Success Criteria

### Phase 1 (Foundation)
- [ ] Scanner service container builds and starts
- [ ] All MCP tools respond correctly
- [ ] Dependency scanning finds known vulnerabilities
- [ ] Secret scanning detects test credentials
- [ ] 80%+ unit test coverage
- [ ] Integration tests pass

### Phase 2 (Policy Engine)
- [ ] Policy engine validates all rule types
- [ ] Code scanning (bandit) finds security issues
- [ ] Hot-reload works without restart
- [ ] Scan results persisted and queryable
- [ ] Policy management API functional

### Phase 3 (Workflow Integration)
- [ ] Security gates work in workflow execution
- [ ] Canvas shows security scan nodes
- [ ] Pre-deployment scanning blocks on violations
- [ ] Skill import triggers security scan
- [ ] UI displays scan results

### Phase 4 (Enterprise Features)
- [ ] Container scanning operational
- [ ] SBOM generation produces valid SPDX
- [ ] Security dashboard shows metrics
- [ ] Performance: p95 scan time < 30s
- [ ] Documentation complete

---

## 13. Open Questions

1. **Blocking vs Warning:** Should security gates block deployments or just warn?
2. **Scan Retention:** How long to retain scan results? (Proposed: 90 days)
3. **Custom Rules:** Any organization-specific security policies?
4. **Notifications:** Where should alerts go? (Email, Slack, Dashboard?)
5. **Scope:** Start with Python only, or include JS/TS scanning?
6. **Compliance:** Any specific standards needed? (SOC2, ISO27001?)
7. **Auto-remediation:** Should we implement automatic fixes for simple issues?
8. **Offline Mode:** Need air-gapped scanning capability?

---

## 14. Appendix

### A. Related Documents

- `01-implementation-phases.md` — Phase-by-phase breakdown (authoritative)
- `05-testing-strategy.md` — Testing approach (authoritative)

**Deleted (merged into this document):**
- `02-component-specs.md` — scanner class interfaces, client retry logic, error codes → see §15
- `03-integration-guide.md` — step-by-step integration, RBAC, verification → see §16
- `04-deployment-guide.md` — system requirements, production checklist, K8s → see §17

### B. External References

| Resource | URL | Description |
|----------|-----|-------------|
| MCP Specification | https://spec.modelcontextprotocol.io | MCP protocol spec |
| pip-audit | https://github.com/pypa/pip-audit | Dependency scanner |
| bandit | https://bandit.readthedocs.io | Python SAST |
| detect-secrets | https://github.com/Yelp/detect-secrets | Secret scanner |
| OSV Database | https://osv.dev | Vulnerability database |

### C. Glossary

- **MCP:** Model Context Protocol - JSON-RPC over HTTP+SSE
- **SAST:** Static Application Security Testing
- **SBOM:** Software Bill of Materials
- **CVE:** Common Vulnerabilities and Exposures
- **OSV:** Open Source Vulnerabilities database
- **CWE:** Common Weakness Enumeration

---

---

## 15. Scanner Component Interfaces (from 02-component-specs)

### Error Codes

```python
ERROR_CODES = {
    -32601: "Method not found",
    -32602: "Invalid params",
    -32603: "Internal error",
    -32000: "Scan timeout",
    -32001: "Scanner unavailable",
    -32002: "Invalid policy",
    -32003: "Database error"
}
```

### Key Scanner Classes

| Class | File | External Tool |
|-------|------|--------------|
| `DependencyScanner` | `scanners/dependency_scanner.py` | pip-audit |
| `SecretScanner` | `scanners/secret_scanner.py` | detect-secrets |
| `CodeScanner` | `scanners/code_scanner.py` | bandit |
| `PolicyScanner` | `scanners/policy_scanner.py` | YAML rules engine |

All scanners return a dict with: `status` (passed/failed/error), `scanned_at` (ISO timestamp), `findings` (list), `total_issues` (int), `summary` (str).

### SecurityScanClient — Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=lambda e: isinstance(e, SecurityScanUnavailableError)
)
async def _call_with_retry(self, tool_name: str, arguments: dict) -> dict: ...
```

### Exception Hierarchy

```python
class SecurityScanError(Exception): ...
class SecurityScanTimeoutError(SecurityScanError): ...
class SecurityScanUnavailableError(SecurityScanError): ...
class SecurityViolation(Exception):
    def __init__(self, violations: list[dict]): ...
```

---

## 16. RBAC & Verification (from 03-integration-guide)

### RBAC Permissions to Add (`backend/security/rbac.py`)

```python
SECURITY_PERMISSIONS = {
    "security:scan": "Run security scans",
    "security:admin": "Manage security policies and view all results",
    "security:override": "Bypass security gates (emergency use)",
}

ROLE_PERMISSIONS = {
    "admin": [..., "security:scan", "security:admin", "security:override"],
    "developer": [..., "security:scan"],
    "analyst": [..., "security:scan"],
}
```

### Verification Commands

```bash
# Health check
curl http://localhost:8003/health
# → {"status": "healthy", "version": "1.0.0"}

# Test dependency scan directly
curl -X POST http://localhost:8003/sse \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"scan_dependencies","arguments":{"requirements_txt":"urllib3==1.26.0","severity_threshold":"medium"}},"id":1}'

# Test via backend API
curl -X POST http://localhost:8000/api/security/scan \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"scan_type":"dependencies","resource_type":"skill","resource_id":"test","content":{"requirements_txt":"requests==2.30.0"}}'

# From backend container
docker compose exec backend curl http://security-scanner:8003/health
```

### Troubleshooting Quick Reference

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Scanner won't start | DB connection or missing env var | `docker compose logs security-scanner` |
| Backend can't reach scanner | Not in blitz-net | `docker network inspect blitz-agentos_blitz-net` |
| Migration fails | postgres not healthy or conflict | `docker compose ps postgres; .venv/bin/alembic upgrade head` |
| High memory | Too many concurrent scans | Set `MAX_SCAN_CONCURRENCY=2` |

---

## 17. Deployment & Operations (from 04-deployment-guide)

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Disk | 20 GB | 50 GB SSD |

### Docker Compose Quick Deploy

```bash
docker compose build security-scanner
docker compose run --rm security-scanner alembic upgrade head
docker compose up -d security-scanner
curl http://localhost:8003/health
```

### Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | required | PostgreSQL connection |
| `SCAN_TIMEOUT` | 300 | Max scan seconds |
| `MAX_SCAN_CONCURRENCY` | 5 | Concurrent scans |
| `VULN_DB_UPDATE_INTERVAL` | 86400 | CVE DB refresh (seconds) |
| `RESULT_RETENTION_DAYS` | 90 | Scan result retention |

### Production Checklist

- [ ] SSL/TLS certificates configured
- [ ] Database backups automated (daily pg_dump of secscan_* tables)
- [ ] Monitoring active (Prometheus scrape at `/metrics`)
- [ ] Resource limits set (CPU: 1.0, Memory: 512MB)
- [ ] Network policy: only backend can reach port 8003
- [ ] Non-root user (UID 1000), read-only filesystem
- [ ] Health checks passing before routing traffic
- [ ] Log rotation configured (`max-size: 100m, max-file: 5`)

### Rollback

```bash
docker compose stop security-scanner
# Comment out security-scanner in docker-compose.yml
docker compose up -d
# Database rollback if needed:
docker compose run --rm security-scanner alembic downgrade -1
```

---

*Document Version: 2.0 (consolidated)*
*Status: Ready for Implementation*
*Last Updated: 2026-03-12*
