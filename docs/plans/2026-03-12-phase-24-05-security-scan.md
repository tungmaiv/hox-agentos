# Phase 24-05: Security Scan Module Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone `security-scanner` Docker service with pip-audit, detect-secrets, and bandit scanners; wire it into the skill import pipeline via `SecurityScanClient`; replace `WeightedSecurityScanner`; add configurable block/warn/log per policy severity.

**Architecture:** `infra/security-scanner/` is a FastAPI service exposing `POST /scan` with scan_type dispatch. `backend/mcp/security_scan_client.py` calls it. `skills/adapters/unified_import.py` gates imports through it. Policies live in `secscan_policies` DB table; `error` severity blocks, `warning` sets `pending_review`, `info` logs only.

**Tech Stack:** Python 3.12, FastAPI, pip-audit, detect-secrets, bandit, SQLAlchemy async, docker-compose.yml addition. Alembic migrations 030 (secscan tables).

**Depends on:** Phase 24-02 (registry_entries), Phase 24-04 (UnifiedImportService stub to replace).

---

## Task 1: Create `infra/security-scanner/` Skeleton

**Files:**
- Create: `infra/security-scanner/main.py`
- Create: `infra/security-scanner/config.py`
- Create: `infra/security-scanner/pyproject.toml`
- Create: `infra/security-scanner/Dockerfile`

**Step 1: Create pyproject.toml**

```toml
# infra/security-scanner/pyproject.toml
[project]
name = "security-scanner"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "structlog>=24.0",
    "asyncpg>=0.29",
    "sqlalchemy[asyncio]>=2.0",
    "pip-audit>=2.7",
    "detect-secrets>=1.5",
    "bandit>=1.8",
]
```

**Step 2: Create config.py**

```python
# infra/security-scanner/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://blitz:blitz@postgres/blitz"
    scan_timeout: int = 300
    max_concurrency: int = 5
    log_level: str = "info"

    model_config = {"env_file": ".env"}


settings = Settings()
```

**Step 3: Create main.py**

```python
# infra/security-scanner/main.py
"""
Security Scanner Service — MCP-compatible FastAPI service.

Endpoints:
  GET  /health         — liveness
  POST /scan           — run one or more scanners on submitted content
  GET  /policies       — list active policies
  POST /policies       — create a policy
"""
import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any

from scanners.dependency_scanner import DependencyScanner
from scanners.secret_scanner import SecretScanner
from scanners.code_scanner import CodeScanner

logger = structlog.get_logger(__name__)

app = FastAPI(title="Blitz Security Scanner")

_dep_scanner = DependencyScanner()
_secret_scanner = SecretScanner()
_code_scanner = CodeScanner()


class ScanRequest(BaseModel):
    scan_type: str           # "dependency" | "secret" | "code" | "all"
    resource_id: str | None = None
    requirements_txt: str | None = None
    source_code: str | None = None
    file_path: str | None = None
    severity_threshold: str = "medium"  # "low" | "medium" | "high" | "critical"


class ScanResult(BaseModel):
    scan_type: str
    status: str              # "passed" | "failed" | "error"
    findings: list[dict[str, Any]]
    summary: str
    severity_counts: dict[str, int]


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy", "version": "0.1.0"}


@app.post("/scan")
async def scan(req: ScanRequest) -> dict[str, ScanResult]:
    results: dict[str, ScanResult] = {}

    if req.scan_type in ("dependency", "all") and req.requirements_txt:
        results["dependency"] = await _dep_scanner.scan(
            req.requirements_txt, req.severity_threshold
        )

    if req.scan_type in ("secret", "all") and req.source_code:
        results["secret"] = await _secret_scanner.scan(
            req.source_code, req.file_path or "unknown.py"
        )

    if req.scan_type in ("code", "all") and req.source_code:
        results["code"] = await _code_scanner.scan(req.source_code)

    if not results:
        raise HTTPException(
            status_code=400,
            detail=f"No scanner matched scan_type={req.scan_type!r} with provided content",
        )

    return results
```

**Step 4: Create Dockerfile**

```dockerfile
# infra/security-scanner/Dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv --no-cache-dir

WORKDIR /app
COPY pyproject.toml .
RUN uv pip install --system fastapi uvicorn pydantic pydantic-settings structlog \
    pip-audit detect-secrets bandit

COPY . .

RUN useradd -m -u 1000 scanner
USER scanner

EXPOSE 8003
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
```

**Step 5: Create `scanners/__init__.py`**

```python
# infra/security-scanner/scanners/__init__.py
```

**Step 6: Commit**

```bash
git add infra/security-scanner/
git commit -m "feat(24-05): add security-scanner service skeleton"
```

---

## Task 2: DependencyScanner

**Files:**
- Create: `infra/security-scanner/scanners/dependency_scanner.py`

**Step 1: Write the scanner**

```python
# infra/security-scanner/scanners/dependency_scanner.py
"""
DependencyScanner — runs pip-audit on provided requirements.txt content.
Writes a temporary requirements.txt, invokes pip-audit as a subprocess,
parses JSON output, returns structured findings.
"""
import asyncio
import json
import tempfile
import os
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0}


class DependencyScanner:
    async def scan(
        self, requirements_txt: str, severity_threshold: str = "medium"
    ) -> dict[str, Any]:
        """Scan requirements.txt content for known CVEs via pip-audit.

        Returns ScanResult-compatible dict.
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write(requirements_txt)
            tmp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "pip-audit", "-r", tmp_path, "--format=json", "--no-deps",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120.0)
        finally:
            os.unlink(tmp_path)

        findings = []
        severity_counts: dict[str, int] = {
            "critical": 0, "high": 0, "medium": 0, "low": 0
        }

        if stdout:
            try:
                audit_data = json.loads(stdout.decode())
                for dep in audit_data.get("dependencies", []):
                    for vuln in dep.get("vulns", []):
                        severity = self._classify_severity(vuln)
                        severity_counts[severity] = severity_counts.get(severity, 0) + 1
                        findings.append({
                            "type": "vulnerability",
                            "severity": severity,
                            "package": dep.get("name"),
                            "version": dep.get("version"),
                            "vuln_id": vuln.get("id"),
                            "description": vuln.get("description", ""),
                            "fix_versions": vuln.get("fix_versions", []),
                        })
            except json.JSONDecodeError:
                pass  # pip-audit may exit non-zero with no JSON on clean scan

        # Filter findings by threshold
        threshold_level = _SEVERITY_ORDER.get(severity_threshold, 2)
        filtered = [
            f for f in findings
            if _SEVERITY_ORDER.get(f["severity"], 0) >= threshold_level
        ]

        status = "failed" if filtered else "passed"
        return {
            "scan_type": "dependency",
            "status": status,
            "findings": filtered,
            "summary": f"Found {len(filtered)} vulnerabilities at or above {severity_threshold} severity",
            "severity_counts": severity_counts,
        }

    def _classify_severity(self, vuln: dict) -> str:
        aliases = vuln.get("aliases", [])
        # CVSS scoring not available from pip-audit; default to "high" for known CVEs
        vuln_id = vuln.get("id", "").upper()
        if vuln_id.startswith("GHSA") or vuln_id.startswith("CVE"):
            return "high"
        return "medium"
```

**Step 2: Create a simple test**

```python
# infra/security-scanner/tests/test_dependency_scanner.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_dependency_scanner_clean_requirements():
    from scanners.dependency_scanner import DependencyScanner

    # Mock pip-audit returning no vulnerabilities
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(
            b'{"dependencies": [], "fix_versions": []}', b""
        ))
        mock_exec.return_value = mock_proc

        scanner = DependencyScanner()
        result = await scanner.scan("requests==2.31.0")
        assert result["status"] == "passed"
        assert result["findings"] == []
```

**Step 3: Commit**

```bash
git add infra/security-scanner/scanners/dependency_scanner.py \
        infra/security-scanner/tests/
git commit -m "feat(24-05): add DependencyScanner using pip-audit"
```

---

## Task 3: SecretScanner and CodeScanner

**Files:**
- Create: `infra/security-scanner/scanners/secret_scanner.py`
- Create: `infra/security-scanner/scanners/code_scanner.py`

**Step 1: Write SecretScanner**

```python
# infra/security-scanner/scanners/secret_scanner.py
"""SecretScanner — uses detect-secrets to find credentials in source code."""
import json
import subprocess
import tempfile
import os
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SecretScanner:
    async def scan(self, source_code: str, file_path: str = "unknown.py") -> dict[str, Any]:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=os.path.splitext(file_path)[1] or ".py", delete=False
        ) as f:
            f.write(source_code)
            tmp_path = f.name

        try:
            result = subprocess.run(
                ["detect-secrets", "scan", tmp_path, "--json"],
                capture_output=True, text=True, timeout=30
            )
            findings = []
            if result.stdout:
                data = json.loads(result.stdout)
                for fname, secrets in data.get("results", {}).items():
                    for secret in secrets:
                        findings.append({
                            "type": "secret",
                            "severity": "critical",
                            "secret_type": secret.get("type"),
                            "location": f"{file_path}:{secret.get('line_number')}",
                            "hashed_secret": secret.get("hashed_secret"),
                        })
        finally:
            os.unlink(tmp_path)

        status = "failed" if findings else "passed"
        return {
            "scan_type": "secret",
            "status": status,
            "findings": findings,
            "summary": f"Found {len(findings)} potential secrets",
            "severity_counts": {"critical": len(findings)},
        }
```

**Step 2: Write CodeScanner**

```python
# infra/security-scanner/scanners/code_scanner.py
"""CodeScanner — uses bandit for Python static security analysis."""
import json
import subprocess
import tempfile
import os
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_BANDIT_SEVERITY_MAP = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}


class CodeScanner:
    async def scan(self, source_code: str) -> dict[str, Any]:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source_code)
            tmp_path = f.name

        try:
            result = subprocess.run(
                ["bandit", "-f", "json", "-q", tmp_path],
                capture_output=True, text=True, timeout=60
            )
            findings = []
            severity_counts: dict[str, int] = {}
            if result.stdout:
                data = json.loads(result.stdout)
                for issue in data.get("results", []):
                    severity = _BANDIT_SEVERITY_MAP.get(
                        issue.get("issue_severity", "LOW"), "low"
                    )
                    severity_counts[severity] = severity_counts.get(severity, 0) + 1
                    findings.append({
                        "type": "code_issue",
                        "severity": severity,
                        "rule_id": issue.get("test_id"),
                        "message": issue.get("issue_text"),
                        "location": f"line {issue.get('line_number')}",
                        "cwe": issue.get("issue_cwe", {}).get("id"),
                    })
        finally:
            os.unlink(tmp_path)

        status = "failed" if any(
            f["severity"] in ("high", "critical") for f in findings
        ) else "passed"
        return {
            "scan_type": "code",
            "status": status,
            "findings": findings,
            "summary": f"Found {len(findings)} code security issues",
            "severity_counts": severity_counts,
        }
```

**Step 3: Commit**

```bash
git add infra/security-scanner/scanners/
git commit -m "feat(24-05): add SecretScanner (detect-secrets) and CodeScanner (bandit)"
```

---

## Task 4: Add to docker-compose.yml + Alembic Migration 030

**Files:**
- Modify: `docker-compose.yml`
- Create: `backend/alembic/versions/030_secscan_tables.py`

**Step 1: Add service to docker-compose.yml**

```yaml
  security-scanner:
    build: ./infra/security-scanner
    ports:
      - "8003:8003"
    environment:
      - DATABASE_URL=postgresql+asyncpg://blitz:${POSTGRES_PASSWORD}@postgres/blitz
      - SCAN_TIMEOUT=300
      - MAX_CONCURRENCY=5
      - LOG_LEVEL=info
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

**Step 2: Create migration 030**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
.venv/bin/alembic revision -m "030_secscan_tables"
```

Write the upgrade:

```python
def upgrade() -> None:
    op.create_table(
        "secscan_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_id", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.String(20), nullable=False),
        sa.Column("scan_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("findings", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default="'[]'"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("severity_counts", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default="'{}'"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_secscan_results_resource_id", "secscan_results", ["resource_id"])
    op.create_index("ix_secscan_results_created_at", "secscan_results", ["created_at"])

    op.create_table(
        "secscan_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("policy_type", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default="'[]'"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("secscan_policies")
    op.drop_index("ix_secscan_results_created_at")
    op.drop_index("ix_secscan_results_resource_id")
    op.drop_table("secscan_results")
```

**Step 3: Apply migration**

```bash
docker compose exec backend sh -c "cd /app && alembic upgrade head"
```

**Step 4: Commit**

```bash
git add docker-compose.yml \
        backend/alembic/versions/030_secscan_tables.py
git commit -m "feat(24-05): add security-scanner to docker-compose + migration 030"
```

---

## Task 5: `SecurityScanClient` in Backend

**Files:**
- Create: `backend/mcp/security_scan_client.py`
- Test: `backend/tests/mcp/test_security_scan_client.py`

**Step 1: Write the client**

```python
# backend/mcp/security_scan_client.py
"""
SecurityScanClient — calls the security-scanner Docker service.

Replaces WeightedSecurityScanner. Called by UnifiedImportService
and the skill save endpoint to gate imports.
"""
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

SCANNER_URL = "http://security-scanner:8003"


class SecurityScanClient:
    async def scan(
        self,
        scan_type: str,
        resource_id: str | None = None,
        requirements_txt: str | None = None,
        source_code: str | None = None,
        file_path: str | None = None,
        severity_threshold: str = "medium",
    ) -> dict[str, Any]:
        """Run a scan via the security-scanner service.

        Returns dict of {scan_type: ScanResult}.
        Raises httpx.HTTPError on network failure.
        """
        payload: dict[str, Any] = {
            "scan_type": scan_type,
            "severity_threshold": severity_threshold,
        }
        if resource_id:
            payload["resource_id"] = resource_id
        if requirements_txt:
            payload["requirements_txt"] = requirements_txt
        if source_code:
            payload["source_code"] = source_code
        if file_path:
            payload["file_path"] = file_path

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{SCANNER_URL}/scan", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def is_available(self) -> bool:
        """Check if the scanner service is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{SCANNER_URL}/health")
                return resp.status_code == 200
        except Exception:
            return False
```

**Step 2: Write tests**

```python
# backend/tests/mcp/test_security_scan_client.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_scan_calls_scanner_service():
    from mcp.security_scan_client import SecurityScanClient

    mock_response = {"dependency": {"status": "passed", "findings": [], "summary": "clean"}}
    with patch("httpx.AsyncClient") as mock_cls:
        mock_resp = AsyncMock()
        mock_resp.json = AsyncMock(return_value=mock_response)
        mock_resp.raise_for_status = AsyncMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        client = SecurityScanClient()
        result = await client.scan("dependency", requirements_txt="requests==2.31.0")
        assert result == mock_response
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_is_available_returns_false_on_connection_error():
    from mcp.security_scan_client import SecurityScanClient

    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(
            side_effect=Exception("connection refused")
        )
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        client = SecurityScanClient()
        assert await client.is_available() is False
```

**Step 3: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/mcp/test_security_scan_client.py -v
```

**Step 4: Commit**

```bash
git add backend/mcp/security_scan_client.py \
        backend/tests/mcp/test_security_scan_client.py
git commit -m "feat(24-05): add SecurityScanClient calling Docker scanner service"
```

---

## Task 6: Wire Security Gate into `UnifiedImportService`

**Files:**
- Modify: `backend/skills/adapters/unified_import.py`

**Step 1: Replace the stub with the real gate**

Open `backend/skills/adapters/unified_import.py`. Find `_security_gate_stub`. Replace it with:

```python
async def _security_gate(
    candidate: SkillImportCandidate,
) -> tuple[str, list[dict]]:
    """Run security scans and return (action, findings).

    action: "allow" | "pending_review" | "block"
    findings: list of finding dicts from the scanner

    Falls back to "allow" if scanner is unavailable (non-fatal).
    """
    from mcp.security_scan_client import SecurityScanClient

    client = SecurityScanClient()
    if not await client.is_available():
        import structlog
        structlog.get_logger(__name__).warning(
            "security_scanner_unavailable", name=candidate.name
        )
        return "allow", []

    findings_all: list[dict] = []
    has_error = False
    has_warning = False

    # Scan dependencies if declared
    if candidate.declared_dependencies:
        req_txt = "\n".join(candidate.declared_dependencies)
        try:
            result = await client.scan("dependency", requirements_txt=req_txt)
            dep_result = result.get("dependency", {})
            for finding in dep_result.get("findings", []):
                finding["scan_type"] = "dependency"
                findings_all.append(finding)
                sev = finding.get("severity", "low")
                if sev in ("critical", "high"):
                    has_error = True
                elif sev == "medium":
                    has_warning = True
        except Exception:
            pass

    # Scan scripts for secrets and code issues
    for script in candidate.scripts_content:
        source = script.get("source", "")
        if not source:
            continue
        try:
            result = await client.scan(
                "all", source_code=source, file_path=script.get("filename")
            )
            for scan_type, scan_result in result.items():
                for finding in scan_result.get("findings", []):
                    finding["scan_type"] = scan_type
                    findings_all.append(finding)
                    sev = finding.get("severity", "low")
                    if sev == "critical":
                        has_error = True
                    elif sev in ("high", "medium"):
                        has_warning = True
        except Exception:
            pass

    if has_error:
        return "block", findings_all
    elif has_warning:
        return "pending_review", findings_all
    return "allow", findings_all
```

Update `import_skill()` to use the real gate:

```python
action, findings = await _security_gate(candidate)
if action == "block":
    raise ValueError(
        f"Import blocked by security scan. Findings: "
        f"{[f['message'] for f in findings if 'message' in f]}"
    )
status = "pending_review" if action == "pending_review" else "active"
entry = await self._save(candidate, session, imported_by, status=status)
```

Update `_save()` to accept status:

```python
async def _save(
    self, candidate, session, imported_by, status: str = "active"
) -> RegistryEntry:
    # ... existing code ...
    entry.status = status  # set the gated status
```

**Step 2: Delete `WeightedSecurityScanner`**

```bash
rm backend/skills/security_scanner.py
```

Find all callers of `SecurityScanner` / `WeightedSecurityScanner` in the backend:

```bash
grep -r "SecurityScanner\|WeightedSecurityScanner\|security_scanner" \
  backend/ --include="*.py" -l
```

For each caller file, remove the import and replace the scan call with `SecurityScanClient` or stub with `_security_gate`.

**Step 3: Run tests to confirm no regressions**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

**Step 4: Commit**

```bash
git add backend/skills/adapters/unified_import.py
git rm backend/skills/security_scanner.py
git commit -m "feat(24-05): wire real security gate into UnifiedImportService; remove WeightedSecurityScanner"
```

---

## Completion Check

```bash
# Scanner service is healthy
curl http://localhost:8003/health
# → {"status": "healthy", "version": "0.1.0"}

# Backend tests still pass
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
