# Security Scan Module - Testing Strategy

> **Document Type:** Testing Strategy  
> **Status:** Draft  
> **Audience:** QA Engineers, Developers  > **Last Updated:** 2026-03-11

---

## 1. Testing Overview

### 1.1 Testing Pyramid

```
         /\
        /  \
       / E2E\        (5% of tests - Critical paths)
      /────────\
     /Integration\   (15% of tests - Component interactions)
    /──────────────\
   /     Unit        \  (80% of tests - Core logic)
  /────────────────────\
```

### 1.2 Coverage Targets

| Component | Target Coverage | Priority |
|-----------|----------------|----------|
| Scanners | 90% | Critical |
| Policy Engine | 85% | Critical |
| MCP Server | 80% | High |
| Client | 80% | High |
| Database Layer | 75% | Medium |

---

## 2. Unit Testing

### 2.1 Dependency Scanner Tests

**File:** `infra/security-scanner/tests/test_dependency_scanner.py`

```python
"""Tests for dependency scanner."""
import pytest
from scanners.dependency_scanner import DependencyScanner, Vulnerability


@pytest.fixture
def scanner():
    return DependencyScanner()


class TestDependencyScanner:
    """Test cases for dependency scanning."""
    
    async def test_scan_with_no_vulnerabilities(self, scanner):
        """Test scanning safe dependencies."""
        # Arrange
        requirements = "requests==2.31.0\n"
        
        # Act
        result = await scanner.scan(requirements_txt=requirements)
        
        # Assert
        assert result["status"] == "passed"
        assert result["vulnerabilities"] == []
        assert result["total_packages"] == 1
    
    async def test_scan_finds_vulnerability(self, scanner):
        """Test scanning vulnerable dependency."""
        # Arrange
        requirements = "urllib3==1.26.0\n"
        
        # Act
        result = await scanner.scan(requirements_txt=requirements)
        
        # Assert
        assert result["status"] == "failed"
        assert len(result["vulnerabilities"]) > 0
        assert result["vulnerable_packages"] >= 1
    
    async def test_severity_threshold_filtering(self, scanner):
        """Test that severity threshold filters results."""
        # Arrange
        requirements = "urllib3==1.26.0\n"
        
        # Act - High threshold
        result_high = await scanner.scan(
            requirements_txt=requirements,
            severity_threshold="high"
        )
        
        # Act - Low threshold
        result_low = await scanner.scan(
            requirements_txt=requirements,
            severity_threshold="low"
        )
        
        # Assert
        assert len(result_low["vulnerabilities"]) >= len(result_high["vulnerabilities"])
    
    async def test_scan_timeout_handling(self, scanner):
        """Test timeout handling."""
        # Arrange - Large requirements file
        requirements = "\n".join([f"package{i}==1.0.0" for i in range(1000)])
        
        # Act
        result = await scanner.scan(
            requirements_txt=requirements,
            timeout=1  # 1 second timeout
        )
        
        # Assert
        assert result["status"] == "error"
        assert "timeout" in result["summary"].lower()
    
    async def test_empty_requirements(self, scanner):
        """Test scanning empty requirements."""
        # Act
        result = await scanner.scan(requirements_txt="")
        
        # Assert
        assert result["status"] == "passed"
        assert result["total_packages"] == 0
    
    async def test_invalid_requirements_format(self, scanner):
        """Test handling invalid requirements.txt format."""
        # Act
        result = await scanner.scan(requirements_txt="not-valid-requirements")
        
        # Assert
        assert result["status"] in ["passed", "error"]
```

### 2.2 Secret Scanner Tests

**File:** `infra/security-scanner/tests/test_secret_scanner.py`

```python
"""Tests for secret scanner."""
import pytest
from scanners.secret_scanner import SecretScanner


@pytest.fixture
def scanner():
    return SecretScanner()


class TestSecretScanner:
    """Test cases for secret detection."""
    
    async def test_detects_api_key(self, scanner):
        """Test API key detection."""
        # Arrange
        code = "API_KEY = 'sk-1234567890abcdef'"
        
        # Act
        result = await scanner.scan(source_code=code)
        
        # Assert
        assert result["status"] == "failed"
        assert len(result["findings"]) > 0
        assert result["findings"][0]["type"] == "API Key"
    
    async def test_detects_password(self, scanner):
        """Test password detection."""
        # Arrange
        code = "password = 'supersecret123'"
        
        # Act
        result = await scanner.scan(source_code=code)
        
        # Assert
        assert result["status"] == "failed"
        assert any("password" in f["type"].lower() for f in result["findings"])
    
    async def test_secrets_are_hashed(self, scanner):
        """Test that detected secrets are hashed, not exposed."""
        # Arrange
        code = "API_KEY = 'sk-1234567890abcdef'"
        
        # Act
        result = await scanner.scan(source_code=code)
        
        # Assert
        assert "sk-1234567890abcdef" not in str(result)
        assert "hashed_secret" in result["findings"][0]
    
    async def test_no_secrets_in_clean_code(self, scanner):
        """Test that clean code passes."""
        # Arrange
        code = """
def hello():
    return "Hello World"
"""
        
        # Act
        result = await scanner.scan(source_code=code)
        
        # Assert
        assert result["status"] == "passed"
        assert result["total_issues"] == 0
    
    async def test_quick_vs_deep_scan(self, scanner):
        """Test that deep scan finds more than quick scan."""
        # Arrange
        code = """
# Hidden base64 encoded secret
encoded = 'c2stMTIzNDU2Nzg5MA=='
"""
        
        # Act
        quick_result = await scanner.scan(source_code=code, scan_type="quick")
        deep_result = await scanner.scan(source_code=code, scan_type="deep")
        
        # Assert - Deep scan should find more
        assert deep_result["total_issues"] >= quick_result["total_issues"]
```

### 2.3 Policy Engine Tests

**File:** `infra/security-scanner/tests/test_policy_engine.py`

```python
"""Tests for policy engine."""
import pytest
from scanners.policy_scanner import PolicyScanner, Policy, PolicyRule


@pytest.fixture
def scanner():
    return PolicyScanner()


class TestPolicyEngine:
    """Test cases for policy validation."""
    
    async def test_threshold_rule_pass(self, scanner):
        """Test threshold rule when under limit."""
        # Arrange
        policy = Policy(
            policy_id="test-policy",
            rules=[
                PolicyRule(
                    rule_id="max-critical",
                    rule_type="threshold",
                    severity="error",
                    config={"metric": "critical_vulns", "max_value": 5},
                    message="Too many critical vulnerabilities"
                )
            ]
        )
        resource = {"critical_vulns": 3}
        
        # Act
        result = await scanner.validate_with_policy(policy, resource)
        
        # Assert
        assert result["status"] == "passed"
    
    async def test_threshold_rule_fail(self, scanner):
        """Test threshold rule when over limit."""
        # Arrange
        policy = Policy(
            policy_id="test-policy",
            rules=[
                PolicyRule(
                    rule_id="max-critical",
                    rule_type="threshold",
                    severity="error",
                    config={"metric": "critical_vulns", "max_value": 0},
                    message="Critical vulnerabilities not allowed"
                )
            ]
        )
        resource = {"critical_vulns": 1}
        
        # Act
        result = await scanner.validate_with_policy(policy, resource)
        
        # Assert
        assert result["status"] == "failed"
        assert len(result["violations"]) == 1
    
    async def test_blocklist_rule(self, scanner):
        """Test blocklist rule."""
        # Arrange
        policy = Policy(
            policy_id="test-policy",
            rules=[
                PolicyRule(
                    rule_id="no-admin-tools",
                    rule_type="blocklist",
                    severity="error",
                    config={
                        "field": "tools",
                        "blocked_items": ["admin.*"],
                        "match_type": "glob"
                    },
                    message="Admin tools not allowed"
                )
            ]
        )
        resource = {"tools": ["admin.delete_user", "email.send"]}
        
        # Act
        result = await scanner.validate_with_policy(policy, resource)
        
        # Assert
        assert result["status"] == "failed"
        assert any("admin.delete_user" in str(v) for v in result["violations"])
    
    async def test_regex_rule(self, scanner):
        """Test regex pattern rule."""
        # Arrange
        policy = Policy(
            policy_id="test-policy",
            rules=[
                PolicyRule(
                    rule_id="no-eval",
                    rule_type="regex",
                    severity="error",
                    config={
                        "field": "source_code",
                        "pattern": "eval\\s*\\("
                    },
                    message="eval() is dangerous"
                )
            ]
        )
        resource = {"source_code": "result = eval(user_input)"}
        
        # Act
        result = await scanner.validate_with_policy(policy, resource)
        
        # Assert
        assert result["status"] == "failed"
    
    async def test_multiple_rules_all_must_pass(self, scanner):
        """Test that all rules must pass for overall pass."""
        # Arrange
        policy = Policy(
            policy_id="test-policy",
            rules=[
                PolicyRule(
                    rule_id="rule-1",
                    rule_type="threshold",
                    severity="error",
                    config={"metric": "vulns", "max_value": 5},
                    message="Too many vulnerabilities"
                ),
                PolicyRule(
                    rule_id="rule-2",
                    rule_type="threshold",
                    severity="error",
                    config={"metric": "secrets", "max_value": 0},
                    message="No secrets allowed"
                )
            ]
        )
        resource = {"vulns": 3, "secrets": 1}
        
        # Act
        result = await scanner.validate_with_policy(policy, resource)
        
        # Assert
        assert result["status"] == "failed"
        assert len(result["violations"]) == 1  # Only secrets rule fails
    
    async def test_policy_hot_reload(self, scanner):
        """Test that policies can be reloaded without restart."""
        # Arrange
        initial_policy_count = len(scanner.policies)
        
        # Act - Add new policy file
        # (Simulate by directly modifying scanner)
        scanner._load_policies()
        
        # Assert
        assert len(scanner.policies) >= initial_policy_count
```

---

## 3. Integration Testing

### 3.1 MCP Server Integration

**File:** `infra/security-scanner/tests/integration/test_mcp_server.py`

```python
"""Integration tests for MCP server."""
import pytest
from httpx import AsyncClient
from main import app


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


class TestMCPServer:
    """Integration tests for MCP protocol."""
    
    async def test_tools_list(self, client):
        """Test tools/list endpoint."""
        # Act
        response = await client.post("/sse", json={
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1
        })
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert "result" in data
        assert "tools" in data["result"]
        assert len(data["result"]["tools"]) > 0
    
    async def test_scan_dependencies_tool(self, client):
        """Test scan_dependencies tool execution."""
        # Act
        response = await client.post("/sse", json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "scan_dependencies",
                "arguments": {
                    "requirements_txt": "requests==2.31.0",
                    "severity_threshold": "medium"
                }
            },
            "id": 2
        })
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "status" in data["result"]
    
    async def test_invalid_tool_name(self, client):
        """Test error handling for invalid tool."""
        # Act
        response = await client.post("/sse", json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "invalid_tool",
                "arguments": {}
            },
            "id": 3
        })
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32601
    
    async def test_health_endpoint(self, client):
        """Test health check endpoint."""
        # Act
        response = await client.get("/health")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
```

### 3.2 Backend Integration

**File:** `backend/tests/integration/test_security_scan_integration.py`

```python
"""Integration tests for backend security scan integration."""
import pytest
from mcp.security_scan_client import SecurityScanClient


@pytest.fixture
def client():
    return SecurityScanClient("http://security-scanner:8003")


class TestBackendIntegration:
    """Integration tests for security scan client."""
    
    async def test_end_to_end_dependency_scan(self, client):
        """Test full dependency scan flow."""
        # Arrange
        requirements = """
requests==2.31.0
urllib3==2.0.0
"""
        
        # Act
        result = await client.scan_dependencies(
            requirements_txt=requirements,
            severity_threshold="medium"
        )
        
        # Assert
        assert "status" in result
        assert "vulnerabilities" in result
        assert "scanned_at" in result
        assert isinstance(result["vulnerabilities"], list)
    
    async def test_end_to_end_secret_scan(self, client):
        """Test full secret scan flow."""
        # Arrange
        code = "API_KEY = 'sk-test123456789'"
        
        # Act
        result = await client.scan_secrets(
            source_code=code,
            scan_type="quick"
        )
        
        # Assert
        assert result["status"] == "failed"
        assert len(result["findings"]) > 0
    
    async def test_scan_result_storage(self, client, db_session):
        """Test that scan results are stored in database."""
        # Arrange
        from database.repository import ScanRepository
        
        repo = ScanRepository(db_session)
        
        # Act
        result = await client.scan_dependencies(
            requirements_txt="requests==2.31.0"
        )
        
        # Save to database
        saved = await repo.save_scan_result(
            resource_id="test-resource",
            resource_type="skill",
            scan_type="dependencies",
            status=result["status"],
            findings=result.get("vulnerabilities", []),
            summary=result["summary"]
        )
        
        # Assert
        assert saved.id is not None
        
        # Retrieve
        history = await repo.get_scan_history("test-resource")
        assert len(history) > 0
```

### 3.3 Database Integration

**File:** `infra/security-scanner/tests/integration/test_database.py`

```python
"""Integration tests for database layer."""
import pytest
from database.repository import ScanRepository, PolicyRepository
from database.models import SecScanResult, SecScanPolicy


class TestDatabaseIntegration:
    """Database integration tests."""
    
    async def test_save_and_retrieve_scan_result(self, db_session):
        """Test saving and retrieving scan results."""
        # Arrange
        repo = ScanRepository(db_session)
        
        # Act
        saved = await repo.save_scan_result(
            resource_id="skill-123",
            resource_type="skill",
            scan_type="dependencies",
            status="failed",
            findings=[
                {"package": "urllib3", "severity": "high"}
            ],
            summary="Found 1 vulnerability"
        )
        
        # Assert
        assert saved.id is not None
        assert saved.resource_id == "skill-123"
        
        # Retrieve
        history = await repo.get_scan_history("skill-123")
        assert len(history) == 1
        assert history[0].status == "failed"
    
    async def test_scan_result_pagination(self, db_session):
        """Test pagination of scan history."""
        # Arrange
        repo = ScanRepository(db_session)
        
        # Save multiple results
        for i in range(10):
            await repo.save_scan_result(
                resource_id="skill-123",
                resource_type="skill",
                scan_type="dependencies",
                status="passed",
                findings=[],
                summary=f"Scan {i}"
            )
        
        # Act
        page1 = await repo.get_scan_history("skill-123", limit=5, offset=0)
        page2 = await repo.get_scan_history("skill-123", limit=5, offset=5)
        
        # Assert
        assert len(page1) == 5
        assert len(page2) == 5
    
    async def test_old_scan_cleanup(self, db_session):
        """Test deletion of old scan results."""
        # Arrange
        repo = ScanRepository(db_session)
        
        # Save old result
        old_result = SecScanResult(
            resource_id="old-skill",
            resource_type="skill",
            scan_type="dependencies",
            status="passed",
            created_at=datetime.utcnow() - timedelta(days=100)
        )
        db_session.add(old_result)
        await db_session.commit()
        
        # Act
        deleted = await repo.delete_old_scans(retention_days=90)
        
        # Assert
        assert deleted > 0
```

---

## 4. End-to-End Testing

### 4.1 Workflow Security Gates

**File:** `tests/e2e/test_security_workflows.py`

```python
"""End-to-end tests for security workflow integration."""
import pytest


class TestSecurityWorkflows:
    """E2E tests for workflow security gates."""
    
    @pytest.mark.e2e
    async def test_workflow_with_security_gate_pass(self, api_client):
        """Test workflow with passing security gate."""
        # Arrange
        workflow = {
            "schema_version": "1.0",
            "nodes": [
                {
                    "id": "security-1",
                    "type": "security_scan",
                    "data": {
                        "policy_id": "default",
                        "fail_on": "error"
                    }
                },
                {
                    "id": "action-1",
                    "type": "tool",
                    "data": {"tool": "email.send"}
                }
            ],
            "edges": [
                {"source": "security-1", "target": "action-1"}
            ]
        }
        
        # Act
        response = await api_client.post("/api/workflows", json=workflow)
        workflow_id = response.json()["id"]
        
        run_response = await api_client.post(
            f"/api/workflows/{workflow_id}/run",
            json={"params": {}}
        )
        
        # Assert
        assert run_response.status_code == 200
        result = run_response.json()
        assert result["status"] != "blocked"
    
    @pytest.mark.e2e
    async def test_workflow_blocked_by_security_gate(self, api_client):
        """Test workflow blocked by failing security gate."""
        # Arrange - Create workflow with vulnerable dependency
        workflow = {
            "schema_version": "1.0",
            "nodes": [
                {
                    "id": "security-1",
                    "type": "security_scan",
                    "data": {
                        "policy_id": "strict",
                        "fail_on": "error"
                    }
                }
            ],
            "context": {
                "dependencies": "urllib3==1.26.0"  # Known vulnerable
            }
        }
        
        # Act
        response = await api_client.post("/api/workflows", json=workflow)
        workflow_id = response.json()["id"]
        
        run_response = await api_client.post(
            f"/api/workflows/{workflow_id}/run",
            json={"params": {}}
        )
        
        # Assert
        result = run_response.json()
        assert result["status"] == "blocked"
        assert "security" in result["stop_reason"].lower()

    @pytest.mark.e2e
    async def test_skill_import_security_scan(self, api_client):
        """Test skill import with security scanning."""
        # Arrange
        skill_data = {
            "name": "test-skill",
            "dependencies": "requests==2.30.0",
            "scripts": [
                {"filename": "main.py", "source": "API_KEY = 'secret123'"}
            ]
        }
        
        # Act
        response = await api_client.post(
            "/api/skills/import",
            json=skill_data
        )
        
        # Assert - Should fail due to hardcoded secret
        assert response.status_code == 400
        assert "secret" in response.json()["error"].lower()
```

---

## 5. Performance Testing

### 5.1 Load Testing

**File:** `tests/performance/test_scan_performance.py`

```python
"""Performance tests for security scanning."""
import pytest
import time
from concurrent.futures import ThreadPoolExecutor


class TestScanPerformance:
    """Performance benchmarks for scanners."""
    
    async def test_dependency_scan_performance(self, scanner):
        """Test dependency scan completes within acceptable time."""
        # Arrange
        requirements = "\n".join([f"package{i}==1.0.0" for i in range(50)])
        
        # Act
        start = time.time()
        result = await scanner.scan(requirements_txt=requirements)
        elapsed = time.time() - start
        
        # Assert
        assert elapsed < 30, f"Scan took {elapsed}s, expected <30s"
        assert result["status"] in ["passed", "failed"]
    
    async def test_concurrent_scan_performance(self, scanner):
        """Test system handles concurrent scans."""
        # Arrange
        requirements = "requests==2.31.0"
        max_concurrent = 5
        
        # Act
        start = time.time()
        
        tasks = [
            scanner.scan(requirements_txt=requirements)
            for _ in range(max_concurrent)
        ]
        results = await asyncio.gather(*tasks)
        
        elapsed = time.time() - start
        
        # Assert
        assert all(r["status"] in ["passed", "failed"] for r in results)
        # Should complete in roughly same time as single scan (parallel)
        assert elapsed < 60, f"Concurrent scans took {elapsed}s"
    
    async def test_memory_usage(self, scanner):
        """Test scan memory usage stays within limits."""
        import psutil
        import os
        
        # Arrange
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Act - Run large scan
        large_requirements = "\n".join([f"package{i}==1.0.0" for i in range(100)])
        await scanner.scan(requirements_txt=large_requirements)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Assert
        assert memory_increase < 100, f"Memory increased by {memory_increase}MB"
```

### 5.2 Benchmarks

**Target Performance:**

| Operation | Target | Maximum |
|-----------|--------|---------|
| Dependency scan (50 packages) | < 10s | 30s |
| Secret scan (1000 lines) | < 5s | 15s |
| Code scan (1000 lines) | < 10s | 30s |
| Policy validation | < 1s | 5s |
| Concurrent scans (5) | < 30s | 60s |

---

## 6. Security Testing

### 6.1 Scanner Security

**File:** `tests/security/test_scanner_security.py`

```python
"""Security tests for the scanner service."""
import pytest


class TestScannerSecurity:
    """Security-focused tests."""
    
    async def test_secrets_not_logged(self, scanner, caplog):
        """Test that detected secrets don't appear in logs."""
        # Arrange
        code = "API_KEY = 'sk-secret123456789'"
        
        # Act
        with caplog.at_level("INFO"):
            result = await scanner.scan_secrets(source_code=code)
        
        # Assert
        assert "sk-secret123456789" not in caplog.text
        assert result["findings"][0]["hashed_secret"] is not None
    
    async def test_no_sql_injection_in_resource_id(self, repo):
        """Test that resource IDs are properly sanitized."""
        # Arrange
        malicious_id = "'; DROP TABLE secscan_results; --"
        
        # Act - Should not raise or cause injection
        try:
            history = await repo.get_scan_history(malicious_id)
            # Should return empty list, not crash
            assert isinstance(history, list)
        except Exception as e:
            # Should not be SQL-related error
            assert "sql" not in str(e).lower()
    
    async def test_timeout_prevents_resource_exhaustion(self, scanner):
        """Test that timeouts prevent DoS via slow scans."""
        # Arrange - Create input that would take long to scan
        large_input = "x" * 10000000  # 10MB of data
        
        # Act
        result = await scanner.scan(
            source_code=large_input,
            timeout=1  # 1 second timeout
        )
        
        # Assert - Should timeout gracefully
        assert result["status"] == "error"
        assert "timeout" in result["summary"].lower()
```

---

## 7. Test Data

### 7.1 Fixtures

**File:** `tests/conftest.py`

```python
"""Test fixtures."""
import pytest
from database.models import SecScanPolicy


@pytest.fixture
def sample_policy():
    """Sample security policy for testing."""
    return {
        "policy_id": "test-policy",
        "name": "Test Policy",
        "policy_type": "dependency",
        "rules": [
            {
                "rule_id": "max-critical",
                "rule_type": "threshold",
                "severity": "error",
                "config": {"metric": "critical_vulns", "max_value": 0},
                "message": "No critical vulnerabilities allowed"
            }
        ]
    }


@pytest.fixture
def vulnerable_requirements():
    """Requirements with known vulnerabilities."""
    return """
urllib3==1.26.0
requests==2.30.0
"""


@pytest.fixture
def safe_requirements():
    """Requirements with no known vulnerabilities."""
    return """
requests==2.31.0
urllib3==2.0.0
"""


@pytest.fixture
def code_with_secrets():
    """Source code containing secrets."""
    return """
API_KEY = 'sk-1234567890abcdef'
PASSWORD = 'supersecret123'
TOKEN = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
"""


@pytest.fixture
def code_with_security_issues():
    """Source code with security issues."""
    return """
import os

def run_command(user_input):
    # B605: Starting a process with a shell
    os.system(f"echo {user_input}")
    
    # B307: Use of possibly insecure function
    result = eval(user_input)
    
    # B105: Hardcoded password string
    password = "secret123"
"""
```

---

## 8. CI/CD Integration

### 8.1 GitHub Actions Workflow

**File:** `.github/workflows/security-scanner-tests.yml`

```yaml
name: Security Scanner Tests

on:
  push:
    paths:
      - 'infra/security-scanner/**'
      - 'backend/mcp/security_scan_client.py'
  pull_request:
    paths:
      - 'infra/security-scanner/**'

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        cd infra/security-scanner
        pip install -e ".[test]"
    
    - name: Run unit tests
      run: |
        cd infra/security-scanner
        pytest tests/unit -v --cov=scanners --cov-report=xml
      env:
        DATABASE_URL: postgresql://test:test@localhost:5432/test
    
    - name: Run integration tests
      run: |
        cd infra/security-scanner
        pytest tests/integration -v
      env:
        DATABASE_URL: postgresql://test:test@localhost:5432/test
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        files: infra/security-scanner/coverage.xml
        flags: security-scanner
```

---

## 9. Test Environments

### 9.1 Local Development

```bash
# Run all tests
cd infra/security-scanner
pytest

# Run with coverage
pytest --cov=scanners --cov-report=html

# Run specific test file
pytest tests/test_dependency_scanner.py -v

# Run with debugging
pytest tests/test_dependency_scanner.py -v --pdb
```

### 9.2 Docker Test Environment

```bash
# Run tests in Docker
docker compose -f docker-compose.test.yml up --abort-on-container-exit

# Or run manually
docker compose exec security-scanner pytest
```

### 9.3 CI Environment

Tests run automatically on:
- Every PR affecting security scanner code
- Nightly builds
- Before releases

---

## 10. Quality Gates

### 10.1 Pre-Merge Requirements

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Code coverage >= 80%
- [ ] No security vulnerabilities (bandit)
- [ ] No code style issues (black, ruff)
- [ ] Type checking passes (mypy)

### 10.2 Pre-Release Requirements

- [ ] All E2E tests pass
- [ ] Performance benchmarks met
- [ ] Load testing completed
- [ ] Security audit passed
- [ ] Documentation updated

---

*Document Version: 1.0*  
*Last Updated: 2026-03-11*
