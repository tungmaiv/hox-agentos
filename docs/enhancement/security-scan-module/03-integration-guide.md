# Security Scan Module - Integration Guide

> **Document Type:** Integration Guide  
> **Status:** Draft  
> **Audience:** Backend Engineers, DevOps  
> **Last Updated:** 2026-03-11

---

## 1. Overview

This guide provides step-by-step instructions for integrating the Security Scan Module with Blitz AgentOS.

### Integration Points

1. **Backend Integration** - Tool registration, client setup, API routes
2. **Workflow Integration** - Security gates in workflows
3. **Skill Import Integration** - Pre-import security scanning
4. **Frontend Integration** - UI components for security features
5. **Database Integration** - Shared PostgreSQL setup
6. **Docker Integration** - Service orchestration

---

## 2. Backend Integration

### 2.1 Prerequisites

- AgentOS backend running
- PostgreSQL accessible
- Python 3.12+
- Access to modify `backend/` directory

### 2.2 Step-by-Step Integration

#### Step 1: Create Backend Client

**File:** `backend/mcp/security_scan_client.py`

```python
"""
Client for Security Scanner MCP service.
"""
from typing import Optional, Any
import structlog
from mcp.client import MCPClient

logger = structlog.get_logger(__name__)


class SecurityScanClient:
    """Client for security scanner MCP server."""
    
    def __init__(self, server_url: str = "http://security-scanner:8003"):
        self._client = MCPClient(server_url)
    
    async def scan_dependencies(
        self,
        requirements_txt: Optional[str] = None,
        pyproject_toml: Optional[str] = None,
        severity_threshold: str = "medium"
    ) -> dict[str, Any]:
        """Scan Python dependencies."""
        logger.info("scanning_dependencies", threshold=severity_threshold)
        
        arguments = {"severity_threshold": severity_threshold}
        if requirements_txt:
            arguments["requirements_txt"] = requirements_txt
        if pyproject_toml:
            arguments["pyproject_toml"] = pyproject_toml
        
        result = await self._client.call_tool("scan_dependencies", arguments)
        
        if not result.get("success"):
            raise SecurityScanError(result.get("error", "Unknown error"))
        
        return result.get("result", {})
    
    async def scan_secrets(
        self,
        source_code: str,
        file_path: str = "unknown",
        scan_type: str = "quick"
    ) -> dict[str, Any]:
        """Scan code for secrets."""
        logger.info("scanning_secrets", file_path=file_path)
        
        result = await self._client.call_tool("scan_secrets", {
            "source_code": source_code,
            "file_path": file_path,
            "scan_type": scan_type
        })
        
        if not result.get("success"):
            raise SecurityScanError(result.get("error", "Unknown error"))
        
        return result.get("result", {})
    
    async def validate_policy(
        self,
        resource_type: str,
        resource_data: dict,
        policy_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Validate against security policy."""
        logger.info("validating_policy", resource_type=resource_type)
        
        arguments = {
            "resource_type": resource_type,
            "resource_data": resource_data
        }
        if policy_id:
            arguments["policy_id"] = policy_id
        
        result = await self._client.call_tool("validate_policy", arguments)
        
        if not result.get("success"):
            raise SecurityScanError(result.get("error", "Unknown error"))
        
        return result.get("result", {})


class SecurityScanError(Exception):
    """Raised when security scan fails."""
    pass
```

#### Step 2: Register Security Tools

**File:** `backend/main.py`

Add to the `lifespan()` function:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ... existing startup code ...
    
    # Register security scanner tools
    try:
        from core.db import async_session
        from gateway.tool_registry import register_tool
        
        async with async_session() as session:
            # Register dependency scanner
            await register_tool(
                session,
                name="security.scan_dependencies",
                description="Scan Python dependencies for known vulnerabilities",
                required_permissions=["security:scan"],
                handler_type="mcp",
                mcp_server="security-scanner",
                mcp_tool="scan_dependencies"
            )
            
            # Register secret scanner
            await register_tool(
                session,
                name="security.scan_secrets",
                description="Scan code for secrets and credentials",
                required_permissions=["security:scan"],
                handler_type="mcp",
                mcp_server="security-scanner",
                mcp_tool="scan_secrets"
            )
            
            # Register code scanner
            await register_tool(
                session,
                name="security.scan_code",
                description="Run static code analysis",
                required_permissions=["security:scan"],
                handler_type="mcp",
                mcp_server="security-scanner",
                mcp_tool="scan_code"
            )
            
            # Register policy validator
            await register_tool(
                session,
                name="security.validate_policy",
                description="Validate resource against security policy",
                required_permissions=["security:admin"],
                handler_type="mcp",
                mcp_server="security-scanner",
                mcp_tool="validate_policy"
            )
            
            logger.info("security_scanner_tools_registered")
            
    except Exception as exc:
        logger.warning("security_scanner_registration_failed", error=str(exc))
    
    yield
    # ... existing shutdown code ...
```

#### Step 3: Add RBAC Permissions

**File:** `backend/security/rbac.py`

Add security permissions:

```python
# Add to permission registry
SECURITY_PERMISSIONS = {
    "security:scan": "Run security scans",
    "security:admin": "Manage security policies and view all results",
    "security:override": "Bypass security gates (emergency use)",
}

# Add to role mappings
ROLE_PERMISSIONS = {
    "admin": [
        # ... existing permissions ...
        "security:scan",
        "security:admin",
        "security:override",
    ],
    "developer": [
        # ... existing permissions ...
        "security:scan",
    ],
    "analyst": [
        # ... existing permissions ...
        "security:scan",
    ],
}
```

#### Step 4: Create API Routes

**File:** `backend/api/routes/security_scan.py`

```python
"""
Security scan API routes.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_current_user, require_permissions
from core.schemas.security_scan import (
    ScanRequest,
    ScanResultResponse,
    ScanHistoryResponse,
)
from mcp.security_scan_client import SecurityScanClient, SecurityScanError

router = APIRouter(prefix="/security", tags=["security"])


@router.post("/scan", response_model=ScanResultResponse)
async def trigger_scan(
    request: ScanRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["security:scan"])),
):
    """Trigger a security scan on a resource."""
    client = SecurityScanClient()
    
    try:
        if request.scan_type == "dependencies":
            result = await client.scan_dependencies(
                requirements_txt=request.content.get("requirements_txt"),
                pyproject_toml=request.content.get("pyproject_toml"),
                severity_threshold=request.severity_threshold
            )
        elif request.scan_type == "secrets":
            result = await client.scan_secrets(
                source_code=request.content.get("source_code"),
                file_path=request.content.get("file_path", "unknown"),
                scan_type=request.scan_type
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown scan type: {request.scan_type}")
        
        # Store scan result in database
        # ... repository call ...
        
        return ScanResultResponse(
            scan_id="generated-uuid",
            status="completed",
            result=result,
            created_at=datetime.utcnow()
        )
        
    except SecurityScanError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{resource_id}", response_model=ScanHistoryResponse)
async def get_scan_history(
    resource_id: str,
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get scan history for a resource."""
    # Implementation
    pass
```

#### Step 5: Register Routes

**File:** `backend/main.py`

Add to `create_app()`:

```python
def create_app() -> FastAPI:
    # ... existing code ...
    
    # Register security scan routes
    from api.routes import security_scan
    app.include_router(security_scan.router, prefix="/api")
    
    # ... existing code ...
    return app
```

---

## 3. Workflow Integration

### 3.1 Extend Workflow Schema

**File:** `frontend/src/lib/types.ts`

```typescript
// Extend NodeType
type NodeType = "agent" | "tool" | "mcp" | "hitl" | "security_scan";

// Add security scan configuration
interface SecurityScanConfig {
  policy_id?: string;
  scan_type: "dependency" | "secret" | "code" | "policy";
  fail_on: "error" | "warning" | "never";
  auto_remediate?: boolean;
}

// Extend WorkflowNode.data
interface WorkflowNode {
  id: string;
  type: NodeType;
  position: { x: number; y: number };
  data: {
    label: string;
    // ... existing fields ...
    securityConfig?: SecurityScanConfig;
  };
}
```

### 3.2 Add Security Gate to Execution

**File:** `backend/agents/graphs.py`

```python
async def execute_workflow_node(
    node: WorkflowNode,
    state: BlitzState,
    db: AsyncSession
) -> BlitzState:
    """Execute a workflow node with security checks."""
    
    if node.type == "security_scan":
        config = node.data.get("securityConfig", {})
        
        # Run security scan
        client = SecurityScanClient()
        result = await client.validate_policy(
            resource_type="workflow",
            resource_data=state.workflow_context,
            policy_id=config.get("policy_id")
        )
        
        # Store result in state
        state.last_security_scan = result
        
        # Handle failure
        if result["status"] == "failed":
            fail_on = config.get("fail_on", "error")
            has_errors = any(
                v["severity"] == "error" 
                for v in result.get("violations", [])
            )
            
            if fail_on == "error" and has_errors:
                raise SecurityViolation(
                    f"Security gate failed: {result['summary']}"
                )
            elif fail_on == "warning":
                raise SecurityViolation(
                    f"Security gate failed: {result['summary']}"
                )
            # If fail_on == "never", just log and continue
            
    # ... rest of execution ...
    return state
```

### 3.3 Handle Security Violations

**File:** `backend/agents/graphs.py`

```python
class SecurityViolation(Exception):
    """Workflow blocked by security gate."""
    
    def __init__(self, message: str, violations: list[dict] = None):
        self.message = message
        self.violations = violations or []
        super().__init__(message)


# In workflow execution
try:
    result = await execute_workflow(workflow_id, state)
except SecurityViolation as e:
    # Log violation
    logger.warning("security_violation", 
                   workflow_id=workflow_id,
                   message=e.message,
                   violations=e.violations)
    
    # Store failed run
    await store_workflow_run(
        workflow_id=workflow_id,
        status="blocked",
        stop_reason="security_violation",
        security_violations=e.violations
    )
    
    # Notify user
    await notify_user(
        user_id=state.user_id,
        title="Workflow Blocked",
        message=f"Security violation: {e.message}",
        severity="error"
    )
    
    raise
```

---

## 4. Skill Import Integration

### 4.1 Pre-Import Security Check

**File:** `backend/skill_repos/service.py`

Modify `import_from_repo()`:

```python
async def import_from_repo(
    repo_id: UUID,
    skill_name: str,
    user_id: UUID,
    session: AsyncSession
) -> ImportResponse:
    """Import skill with security scanning."""
    
    # Fetch skill data
    skill_data = await fetch_skill_data(repo_id, skill_name)
    
    # Run security scans
    client = SecurityScanClient()
    security_results = []
    
    # Scan 1: Dependencies
    if skill_data.get("dependencies"):
        dep_result = await client.scan_dependencies(
            requirements_txt=skill_data["dependencies"],
            severity_threshold="medium"
        )
        security_results.append({
            "scan_type": "dependencies",
            "result": dep_result
        })
        
        if dep_result["status"] == "failed":
            critical_count = sum(
                1 for v in dep_result.get("vulnerabilities", [])
                if v.get("severity") == "critical"
            )
            if critical_count > 0:
                return ImportResponse(
                    success=False,
                    error=f"Critical vulnerabilities found: {dep_result['summary']}",
                    security_results=security_results
                )
    
    # Scan 2: Secrets in scripts
    for script in skill_data.get("scripts", []):
        secret_result = await client.scan_secrets(
            source_code=script.get("source", ""),
            file_path=script.get("filename", "unknown"),
            scan_type="deep"
        )
        security_results.append({
            "scan_type": "secrets",
            "file": script.get("filename"),
            "result": secret_result
        })
        
        if secret_result["status"] == "failed":
            return ImportResponse(
                success=False,
                error=f"Secrets detected in {script.get('filename')}",
                security_results=security_results
            )
    
    # Scan 3: Policy validation
    policy_result = await client.validate_policy(
        resource_type="skill",
        resource_data=skill_data
    )
    security_results.append({
        "scan_type": "policy",
        "result": policy_result
    })
    
    if policy_result["status"] == "failed":
        return ImportResponse(
            success=False,
            error=f"Policy validation failed: {policy_result['summary']}",
            security_results=security_results
        )
    
    # Store security results
    await store_security_results(skill_data["id"], security_results)
    
    # Continue with import
    imported_skill = await import_skill_data(skill_data, user_id, session)
    
    return ImportResponse(
        success=True,
        skill_id=imported_skill.id,
        security_results=security_results
    )
```

### 4.2 Security Warning UI

**File:** `frontend/src/components/skills/SecurityWarning.tsx`

```typescript
import React from 'react';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { ShieldAlert, ShieldCheck } from 'lucide-react';

interface SecurityWarningProps {
  results: SecurityScanResult[];
}

export function SecurityWarning({ results }: SecurityWarningProps) {
  const hasViolations = results.some(r => r.result.status === 'failed');
  
  if (!hasViolations) {
    return (
      <Alert variant="default" className="border-green-500">
        <ShieldCheck className="h-4 w-4 text-green-500" />
        <AlertTitle>Security Check Passed</AlertTitle>
        <AlertDescription>
          No security issues detected in this skill.
        </AlertDescription>
      </Alert>
    );
  }
  
  return (
    <Alert variant="destructive">
      <ShieldAlert className="h-4 w-4" />
      <AlertTitle>Security Issues Detected</AlertTitle>
      <AlertDescription>
        <ul className="list-disc pl-4 mt-2">
          {results
            .filter(r => r.result.status === 'failed')
            .map((result, idx) => (
              <li key={idx}>
                <strong>{result.scan_type}:</strong>{' '}
                {result.result.summary}
              </li>
            ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
}
```

---

## 5. Database Integration

### 5.1 Migration Script

**File:** `infra/security-scanner/alembic/versions/001_initial.py`

```python
"""Initial migration for security scanner.

Revision ID: 001
Revises: 
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create secscan_results table
    op.create_table(
        'secscan_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('resource_id', sa.String(255), nullable=False, index=True),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('scan_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('score', sa.Integer, nullable=True),
        sa.Column('findings', postgresql.JSONB(), default=list),
        sa.Column('summary', sa.Text()),
        sa.Column('scanner_version', sa.String(50)),
        sa.Column('policy_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    
    op.create_index('idx_secscan_resource', 'secscan_results', 
                    ['resource_id', 'created_at'])
    
    # Create secscan_policies table
    op.create_table(
        'secscan_policies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('policy_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('rules', postgresql.JSONB(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(),
                  onupdate=sa.func.now()),
    )
    
    # Create secscan_vulnerabilities table
    op.create_table(
        'secscan_vulnerabilities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('vuln_id', sa.String(100), nullable=False, unique=True),
        sa.Column('package_name', sa.String(100), nullable=False, index=True),
        sa.Column('affected_versions', postgresql.JSONB(), default=list),
        sa.Column('fixed_versions', postgresql.JSONB(), default=list),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('aliases', postgresql.JSONB(), default=list),
        sa.Column('published_at', sa.DateTime()),
        sa.Column('updated_in_db_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('secscan_vulnerabilities')
    op.drop_table('secscan_policies')
    op.drop_table('secscan_results')
```

### 5.2 Run Migration

```bash
# Inside security-scanner container
cd /app
alembic upgrade head

# Or from host
docker compose exec security-scanner alembic upgrade head
```

---

## 6. Docker Integration

### 6.1 Add to Docker Compose

**File:** `docker-compose.yml`

```yaml
services:
  # ... existing services ...
  
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

### 6.2 Add Volume

```yaml
volumes:
  # ... existing volumes ...
  security_scanner_data:
```

### 6.3 Build and Start

```bash
# Build the scanner service
docker compose build security-scanner

# Start all services
docker compose up -d

# Verify scanner is running
docker compose ps security-scanner
docker compose logs security-scanner
```

---

## 7. Verification

### 7.1 Health Check

```bash
# Check scanner health
curl http://localhost:8003/health
# Expected: {"status": "healthy", "version": "1.0.0"}

# Check readiness
curl http://localhost:8003/ready
# Expected: {"status": "ready", "checks": {...}}
```

### 7.2 Test Scan

```bash
# Test dependency scan
curl -X POST http://localhost:8003/sse \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "scan_dependencies",
      "arguments": {
        "requirements_txt": "urllib3==1.26.0",
        "severity_threshold": "medium"
      }
    },
    "id": 1
  }'

# Expected: JSON-RPC response with scan results
```

### 7.3 Backend Integration Test

```bash
# Test via backend API
curl -X POST http://localhost:8000/api/security/scan \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "scan_type": "dependencies",
    "resource_type": "skill",
    "resource_id": "test-skill",
    "content": {
      "requirements_txt": "requests==2.30.0"
    }
  }'
```

---

## 8. Troubleshooting

### 8.1 Common Issues

**Issue:** Scanner service won't start
```bash
# Check logs
docker compose logs security-scanner

# Common causes:
# - Database connection failure
# - Missing environment variables
# - Port conflict
```

**Issue:** Backend can't connect to scanner
```bash
# Verify network connectivity
docker compose exec backend curl http://security-scanner:8003/health

# Check if scanner is in blitz-net
docker network inspect blitz-agentos_blitz-net
```

**Issue:** Database migration fails
```bash
# Check if postgres is healthy
docker compose ps postgres

# Run migration manually
docker compose exec security-scanner alembic upgrade head --sql

# Check for conflicts
SELECT * FROM alembic_version;
```

### 8.2 Debug Mode

Enable debug logging:

```yaml
# docker-compose.yml
security-scanner:
  environment:
    - LOG_LEVEL=debug
```

---

## 9. Rollback Procedure

If integration causes issues:

1. **Stop scanner service:**
   ```bash
   docker compose stop security-scanner
   ```

2. **Remove from compose:**
   ```bash
   # Comment out security-scanner service in docker-compose.yml
   ```

3. **Remove backend integration:**
   - Comment out tool registration in `main.py`
   - Remove API routes
   - Remove client code

4. **Revert database:**
   ```bash
   docker compose exec security-scanner alembic downgrade -1
   ```

---

*Document Version: 1.0*  
*Last Updated: 2026-03-11*
