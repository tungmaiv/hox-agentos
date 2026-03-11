# Security Scan Module - Implementation Phases

> **Document Type:** Implementation Roadmap  
> **Status:** Draft  
> **Estimated Timeline:** 8 weeks  
> **Last Updated:** 2026-03-11

---

## Overview

This document breaks down the Security Scan Module implementation into **4 phases** spanning approximately **8 weeks**. Each phase has specific deliverables, success criteria, and dependencies.

---

## Phase 1: Foundation (Weeks 1-2)

**Goal:** Establish the basic scanner service with dependency and secret scanning capabilities.

**Theme:** "Get it working"

### Week 1: Infrastructure & Basic Scanners

#### Plan 01-01: Project Structure & Dockerfile
**Owner:** DevOps/Platform  
**Estimated:** 4 hours

**Tasks:**
1. Create `infra/security-scanner/` directory structure
2. Write `Dockerfile` with multi-stage build
3. Create `pyproject.toml` with dependencies
4. Set up `alembic/` directory for migrations
5. Create initial `README.md`

**Deliverables:**
- Directory structure created
- Dockerfile builds successfully
- Dependencies install without errors

**Success Criteria:**
```bash
# Verify
docker build -t security-scanner:test infra/security-scanner/
docker run --rm security-scanner:test python -c "import fastapi; print('OK')"
```

---

#### Plan 01-02: MCP Server Skeleton
**Owner:** Backend Engineer  
**Estimated:** 8 hours

**Tasks:**
1. Create `main.py` with FastAPI app
2. Implement `/sse` endpoint for MCP JSON-RPC
3. Add `tools/list` handler
4. Add request routing infrastructure
5. Implement health check endpoints (`/health`, `/ready`)
6. Add structured logging with structlog

**Deliverables:**
- MCP server responds to health checks
- `tools/list` returns empty list initially
- Proper error handling for unknown methods

**Success Criteria:**
```bash
# Verify
curl http://localhost:8003/health
# Response: {"status": "healthy"}

curl -X POST http://localhost:8003/sse \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}'
# Response: {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
```

---

#### Plan 01-03: Dependency Scanner
**Owner:** Security Engineer  
**Estimated:** 12 hours

**Tasks:**
1. Create `scanners/dependency_scanner.py`
2. Integrate `pip-audit` library
3. Implement parsing of `requirements.txt`
4. Implement parsing of `pyproject.toml`
5. Add severity threshold filtering
6. Format results according to spec
7. Handle timeouts and errors gracefully
8. Write unit tests

**Deliverables:**
- Dependency scanner finds vulnerabilities
- Severity filtering works
- Results properly structured

**Success Criteria:**
```python
# Test
scanner = DependencyScanner()
result = await scanner.scan(
    requirements_txt="urllib3==1.26.0",
    severity_threshold="medium"
)
assert result["status"] in ["passed", "failed"]
assert "vulnerabilities" in result
assert "summary" in result
```

---

#### Plan 01-04: Secret Scanner
**Owner:** Security Engineer  
**Estimated:** 10 hours

**Tasks:**
1. Create `scanners/secret_scanner.py`
2. Integrate `detect-secrets` library
3. Implement quick and deep scan modes
4. Add support for multiple file types
5. Hash detected secrets for privacy
6. Format results according to spec
7. Handle encoding issues
8. Write unit tests

**Deliverables:**
- Secret scanner detects API keys
- Secret scanner detects passwords
- Secret scanner detects tokens
- Results don't expose actual secrets

**Success Criteria:**
```python
scanner = SecretScanner()
result = await scanner.scan(
    source_code="API_KEY = 'sk-test123456789'",
    scan_type="quick"
)
assert result["status"] == "failed"
assert len(result["findings"]) > 0
assert "hashed_secret" in result["findings"][0]
assert "sk-test" not in str(result)  # Secret not exposed
```

---

### Week 2: Integration & Database

#### Plan 01-05: Database Models & Migrations
**Owner:** Backend Engineer  
**Estimated:** 8 hours

**Tasks:**
1. Create `database/models.py` with SQLAlchemy models
2. Define `SecScanResult` model
3. Define `SecScanPolicy` model (basic)
4. Define `SecScanVulnerability` model (basic)
5. Create Alembic migration files
6. Add database connection configuration
7. Create repository layer for data access
8. Write tests for models

**Deliverables:**
- Database models defined
- Migrations run successfully
- Repository layer functional

**Success Criteria:**
```bash
# Verify migrations
alembic upgrade head
alembic current
# Shows: head (revision)
```

---

#### Plan 01-06: Backend Client Integration
**Owner:** Backend Engineer  
**Estimated:** 10 hours

**Tasks:**
1. Create `backend/mcp/security_scan_client.py`
2. Implement `SecurityScanClient` class
3. Add `scan_dependencies()` method
4. Add `scan_secrets()` method
5. Add error handling and retries
6. Add logging for all operations
7. Write integration tests

**Deliverables:**
- Client can connect to scanner service
- All scan methods work end-to-end
- Proper error handling

**Success Criteria:**
```python
client = SecurityScanClient("http://security-scanner:8003")
result = await client.scan_dependencies(
    requirements_txt="requests==2.30.0"
)
assert "status" in result
assert "vulnerabilities" in result
```

---

#### Plan 01-07: Tool Registration
**Owner:** Backend Engineer  
**Estimated:** 6 hours

**Tasks:**
1. Modify `backend/main.py` to register security tools
2. Add registration to lifespan() function
3. Define tool metadata for all scanners
4. Add required permissions to RBAC
5. Test tool discovery via API
6. Document permission requirements

**Deliverables:**
- Security tools appear in tool registry
- Tools have correct permissions
- Tools discoverable via API

**Success Criteria:**
```bash
# List tools
curl http://localhost:8000/api/tools | jq '.tools[] | select(.name | contains("security"))'
# Should show: security.scan_dependencies, security.scan_secrets
```

---

#### Plan 01-08: Integration Tests
**Owner:** QA Engineer  
**Estimated:** 12 hours

**Tasks:**
1. Set up test infrastructure
2. Write integration tests for dependency scanning
3. Write integration tests for secret scanning
4. Test error scenarios
5. Test timeout handling
6. Add tests to CI pipeline
7. Document test procedures

**Deliverables:**
- Integration test suite passes
- >80% code coverage
- CI pipeline updated

**Success Criteria:**
```bash
# Run tests
pytest tests/integration/security_scanner/ -v
# All tests pass
# Coverage report shows >80%
```

### Phase 1 Success Criteria Checklist

- [ ] Scanner service builds and runs in Docker
- [ ] All health checks pass
- [ ] Dependency scanner finds known vulnerabilities
- [ ] Secret scanner detects test credentials
- [ ] Database migrations run successfully
- [ ] Backend client can call all scanner methods
- [ ] Tools registered in gateway/tool_registry.py
- [ ] Integration tests pass with >80% coverage

---

## Phase 2: Policy Engine & Code Scanning (Weeks 3-4)

**Goal:** Implement policy-based scanning and static code analysis.

**Theme:** "Make it smart"

### Week 3: Policy Engine

#### Plan 02-01: Policy Schema Design
**Owner:** Security Architect  
**Estimated:** 8 hours

**Tasks:**
1. Design YAML policy schema
2. Define rule types (threshold, regex, blocklist, custom)
3. Document schema with examples
4. Create JSON Schema for validation
5. Review with stakeholders
6. Finalize schema design

**Deliverables:**
- Policy schema documented
- Example policies created
- Schema validation defined

**Success Criteria:**
- Schema covers all identified use cases
- Stakeholder approval obtained

---

#### Plan 02-02: Policy Engine Implementation
**Owner:** Security Engineer  
**Estimated:** 16 hours

**Tasks:**
1. Create `scanners/policy_scanner.py`
2. Implement policy loading from YAML
3. Implement rule evaluation engine
4. Add support for threshold rules
5. Add support for blocklist rules
6. Add support for regex rules
7. Implement policy hot-reload
8. Write comprehensive tests

**Deliverables:**
- Policy engine evaluates all rule types
- Hot-reload works without restart
- Default policies loaded on startup

**Success Criteria:**
```python
policy = {
    "rules": [{"rule": "max_critical_vulns", "value": 0, "severity": "error"}]
}
scanner = PolicyScanner()
result = await scanner.validate(resource_type="skill", resource_data=test_data)
assert result["status"] in ["passed", "failed"]
```

---

#### Plan 02-03: Default Policies
**Owner:** Security Architect  
**Estimated:** 6 hours

**Tasks:**
1. Create `policies/default-policies.yaml`
2. Define dependency scanning policy
3. Define secret scanning policy
4. Define skill restriction policy
5. Define workflow validation policy
6. Document each policy
7. Review with security team

**Deliverables:**
- 4-5 default policies defined
- Policies documented
- Security team approval

**Success Criteria:**
- All policies load without errors
- Policies cover critical security concerns

---

### Week 4: Code Scanning & APIs

#### Plan 02-04: Code Scanner (Bandit)
**Owner:** Security Engineer  
**Estimated:** 12 hours

**Tasks:**
1. Create `scanners/code_scanner.py`
2. Integrate `bandit` library
3. Implement Python code scanning
4. Map bandit rules to severity levels
5. Format results according to spec
6. Add support for different rule sets
7. Handle parsing errors gracefully
8. Write unit tests

**Deliverables:**
- Code scanner finds security issues
- Different rule sets supported
- Proper error handling

**Success Criteria:**
```python
scanner = CodeScanner()
result = await scanner.scan(
    source_code="import os\nos.system(user_input)",
    rule_set="default"
)
assert result["status"] == "failed"
assert any("B605" in f.get("rule_id", "") for f in result["findings"])
```

---

#### Plan 02-05: Scan Result Persistence
**Owner:** Backend Engineer  
**Estimated:** 8 hours

**Tasks:**
1. Extend repository layer for scan results
2. Add `save_scan_result()` method
3. Add `get_scan_history()` method
4. Implement result aggregation
5. Add pagination for history queries
6. Implement retention policies
7. Write tests

**Deliverables:**
- Scan results saved to database
- History queries work
- Retention policies enforced

**Success Criteria:**
```python
result = await repository.save_scan_result(scan_data)
assert result.id is not None

history = await repository.get_scan_history(resource_id="skill-123", limit=10)
assert len(history) > 0
```

---

#### Plan 02-06: Policy Management API
**Owner:** Backend Engineer  
**Estimated:** 10 hours

**Tasks:**
1. Create `backend/api/routes/security_scan.py`
2. Implement `GET /api/security/policies`
3. Implement `POST /api/security/policies`
4. Implement `GET /api/security/policies/{id}`
5. Implement `PUT /api/security/policies/{id}`
6. Implement `DELETE /api/security/policies/{id}`
7. Add permission checks
8. Write API tests

**Deliverables:**
- Full CRUD API for policies
- Proper permission enforcement
- API documentation

**Success Criteria:**
```bash
# Create policy
curl -X POST http://localhost:8000/api/security/policies \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "test", "rules": []}'
# Returns 201 Created

# List policies
curl http://localhost:8000/api/security/policies
# Returns list of policies
```

---

#### Plan 02-07: Comprehensive Testing
**Owner:** QA Engineer  
**Estimated:** 12 hours

**Tasks:**
1. Write tests for policy engine
2. Write tests for code scanner
3. Test policy CRUD operations
4. Test permission enforcement
5. Test hot-reload functionality
6. Add performance benchmarks
7. Document test coverage

**Deliverables:**
- All new features tested
- >85% code coverage
- Performance benchmarks established

**Success Criteria:**
```bash
pytest tests/ -v --cov=scanners --cov-report=term-missing
# Coverage: 85%+
# All tests pass
```

### Phase 2 Success Criteria Checklist

- [ ] Policy engine validates all rule types
- [ ] Default policies loaded and functional
- [ ] Code scanner (bandit) finds security issues
- [ ] Scan results persisted to database
- [ ] Policy management API complete
- [ ] Hot-reload works without restart
- [ ] Test coverage >85%

---

## Phase 3: Workflow Integration (Weeks 5-6)

**Goal:** Integrate security scanning into AgentOS workflows and canvas.

**Theme:** "Make it usable"

### Week 5: Workflow Integration

#### Plan 03-01: Workflow Schema Extension
**Owner:** Backend Engineer  
**Estimated:** 8 hours

**Tasks:**
1. Extend `WorkflowDefinition` schema
2. Add `security_scan` node type
3. Define security gate configuration
4. Update TypeScript types
5. Add schema validation
6. Document schema changes

**Deliverables:**
- Workflow schema supports security gates
- TypeScript types updated
- Validation works

**Success Criteria:**
```typescript
// Workflow can include security nodes
const workflow: WorkflowDefinition = {
  schema_version: "1.0",
  nodes: [
    {
      id: "security-1",
      type: "security_scan",
      data: {
        policy_id: "dependency-critical-only",
        fail_on: "error"
      }
    }
  ]
}
```

---

#### Plan 03-02: Canvas Security Node
**Owner:** Frontend Engineer  
**Estimated:** 16 hours

**Tasks:**
1. Create `SecurityScanNode` component
2. Add to React Flow node palette
3. Implement node configuration UI
4. Add policy selector dropdown
5. Add severity threshold selector
6. Style node for visual distinction
7. Write component tests

**Deliverables:**
- Security scan node in canvas
- Configuration UI functional
- Visual design approved

**Success Criteria:**
- User can drag security node to canvas
- User can configure policy and threshold
- Node renders correctly

---

#### Plan 03-03: Workflow Execution Hooks
**Owner:** Backend Engineer  
**Estimated:** 14 hours

**Tasks:**
1. Modify workflow execution engine
2. Add pre-deployment security hook
3. Implement security gate logic
4. Add blocking vs warning modes
5. Handle scan timeouts
6. Store scan results with workflow run
7. Write integration tests

**Deliverables:**
- Security gates execute during workflows
- Blocking mode prevents deployment
- Warning mode logs but continues

**Success Criteria:**
```python
# Workflow with failed security gate
result = await execute_workflow(workflow_with_vulns)
assert result.status == "blocked"
assert "security_violation" in result.stop_reason
```

---

#### Plan 03-04: Skill Import Integration
**Owner:** Backend Engineer  
**Estimated:** 10 hours

**Tasks:**
1. Modify skill import flow
2. Add pre-import security scan
3. Scan dependencies automatically
4. Scan code for secrets
5. Validate against policies
6. Show security warnings in UI
7. Block import on critical violations

**Deliverables:**
- Skill import triggers security scan
- Security warnings displayed
- Critical violations block import

**Success Criteria:**
- Importing skill with secrets shows warning
- Importing skill with critical vulns blocked
- Security results stored with skill

---

### Week 6: UI & Reporting

#### Plan 03-05: Security Violation Reporting
**Owner:** Frontend Engineer  
**Estimated:** 12 hours

**Tasks:**
1. Create violation notification system
2. Add security alerts to UI
3. Create violation detail view
4. Add remediation suggestions
5. Implement dismissal workflow
6. Add audit log for violations
7. Write tests

**Deliverables:**
- Users notified of violations
- Detailed violation information
- Remediation guidance provided

**Success Criteria:**
- User sees security alert in UI
- User can view violation details
- User sees how to fix issue

---

#### Plan 03-06: Scan Results UI
**Owner:** Frontend Engineer  
**Estimated:** 16 hours

**Tasks:**
1. Create `SecurityScanPanel` component
2. Create `ScanResultsTable` component
3. Add vulnerability detail view
4. Implement scan history view
5. Add filtering and sorting
6. Style components consistently
7. Connect to API endpoints

**Deliverables:**
- Security panel in UI
- Scan results displayed
- History view functional

**Success Criteria:**
- User can view all scan results
- User can filter by severity
- User can see scan history

---

#### Plan 03-07: Auto-remediation (Optional)
**Owner:** Security Engineer  
**Estimated:** 12 hours

**Tasks:**
1. Identify auto-fixable issues
2. Implement dependency update suggestions
3. Add secret removal suggestions
4. Create fix application workflow
5. Add confirmation dialogs
6. Test auto-fixes thoroughly

**Deliverables:**
- Auto-remediation suggestions
- User can apply fixes with one click
- Safe, tested fixes only

**Success Criteria:**
- System suggests fix for vulnerable dependency
- User can apply fix
- Fix resolves vulnerability

---

#### Plan 03-08: End-to-End Testing
**Owner:** QA Engineer  
**Estimated:** 16 hours

**Tasks:**
1. Write E2E tests for security gates
2. Test skill import with security scan
3. Test workflow with security nodes
4. Test violation reporting
5. Test scan results UI
6. Performance testing
7. Security testing

**Deliverables:**
- E2E test suite passes
- Performance acceptable
- No security vulnerabilities

**Success Criteria:**
```bash
pytest tests/e2e/test_security_workflows.py -v
# All tests pass
# Average scan time < 10s
```

### Phase 3 Success Criteria Checklist

- [ ] Security gates work in workflow execution
- [ ] Canvas shows security scan nodes
- [ ] Pre-deployment scanning functional
- [ ] Skill import triggers security scan
- [ ] Security violations reported in UI
- [ ] Scan results viewable in dashboard
- [ ] E2E tests pass

---

## Phase 4: Advanced Features (Weeks 7-8)

**Goal:** Add enterprise-grade features.

**Theme:** "Make it enterprise-ready"

### Week 7: Advanced Scanning

#### Plan 04-01: Container Scanning (Trivy)
**Owner:** Security Engineer  
**Estimated:** 16 hours

**Tasks:**
1. Research Trivy integration options
2. Create `scanners/container_scanner.py`
3. Integrate Trivy CLI
4. Implement Dockerfile scanning
5. Implement image scanning
6. Format results consistently
7. Write tests

**Deliverables:**
- Container scanning operational
- Dockerfile issues detected
- Image vulnerabilities found

**Success Criteria:**
```python
scanner = ContainerScanner()
result = await scanner.scan_dockerfile(dockerfile_content)
assert result["status"] in ["passed", "failed"]
assert "vulnerabilities" in result or "findings" in result
```

---

#### Plan 04-02: SBOM Generation
**Owner:** Security Engineer  
**Estimated:** 12 hours

**Tasks:**
1. Research SBOM formats (SPDX, CycloneDX)
2. Implement SBOM generator
3. Support Python packages
4. Support container images
5. Export to SPDX format
6. Store SBOMs in database
7. Add API endpoint for download

**Deliverables:**
- SBOM generation works
- SPDX format supported
- SBOMs downloadable

**Success Criteria:**
```bash
curl http://localhost:8000/api/security/sbom/skill-123 \
  -H "Accept: application/spdx+json"
# Returns valid SPDX JSON
```

---

#### Plan 04-03: License Compliance
**Owner:** Security Engineer  
**Estimated:** 10 hours

**Tasks:**
1. Integrate license scanner
2. Create license policy engine
3. Define allowed/forbidden licenses
4. Scan dependencies for licenses
5. Report license violations
6. Add license whitelist/blacklist

**Deliverables:**
- License scanning works
- Violations detected and reported
- Policy configurable

**Success Criteria:**
- GPL dependencies flagged if policy forbids
- MIT dependencies pass
- License report generated

---

#### Plan 04-04: Security Dashboard
**Owner:** Frontend Engineer  
**Estimated:** 18 hours

**Tasks:**
1. Design security dashboard layout
2. Create vulnerability overview widget
3. Add scan trend charts
4. Create policy compliance widget
5. Add recent violations list
6. Implement drill-down navigation
7. Add export functionality

**Deliverables:**
- Security dashboard page
- Real-time metrics displayed
- Trends visible

**Success Criteria:**
- Dashboard loads in < 2s
- All metrics display correctly
- Charts update in real-time

---

### Week 8: Operations & Polish

#### Plan 04-05: Scan Scheduling (Celery)
**Owner:** Backend Engineer  
**Estimated:** 12 hours

**Tasks:**
1. Create Celery tasks for scanning
2. Implement scheduled scans
3. Add scan queue management
4. Implement retry logic
5. Add scan prioritization
6. Monitor queue depth
7. Write tests

**Deliverables:**
- Scheduled scans work
- Queue management functional
- Retries handled properly

**Success Criteria:**
```python
# Schedule daily scan
from scheduler.celery_app import schedule_security_scan
schedule_security_scan(resource_id="skill-123", cron="0 2 * * *")
```

---

#### Plan 04-06: Metrics & Alerting
**Owner:** DevOps Engineer  
**Estimated:** 10 hours

**Tasks:**
1. Add Prometheus metrics endpoint
2. Define key metrics
3. Create Grafana dashboards
4. Set up alert rules
5. Configure alert channels
6. Test alert delivery
7. Document runbooks

**Deliverables:**
- Metrics endpoint available
- Dashboards created
- Alerts configured

**Success Criteria:**
```bash
curl http://localhost:8003/metrics | grep security_scans_total
# Shows metrics
```

---

#### Plan 04-07: Performance Optimization
**Owner:** Backend Engineer  
**Estimated:** 12 hours

**Tasks:**
1. Profile scan performance
2. Optimize database queries
3. Add result caching
4. Implement parallel scanning
5. Optimize memory usage
6. Set resource limits
7. Document performance characteristics

**Deliverables:**
- p95 scan time < 30s
- Memory usage optimized
- Scalability documented

**Success Criteria:**
- 95th percentile scan time < 30s
- Memory usage < 512MB per scan
- Can handle 10 concurrent scans

---

#### Plan 04-08: Documentation & Runbooks
**Owner:** Technical Writer  
**Estimated:** 16 hours

**Tasks:**
1. Write user documentation
2. Write administrator guide
3. Create troubleshooting runbook
4. Document API reference
5. Create policy writing guide
6. Write deployment procedures
7. Create security runbook

**Deliverables:**
- Complete documentation
- Runbooks for common tasks
- Troubleshooting guide

**Success Criteria:**
- Documentation covers all features
- Runbooks tested and accurate
- New admin can deploy using docs

### Phase 4 Success Criteria Checklist

- [ ] Container scanning operational
- [ ] SBOM generation produces valid SPDX
- [ ] License compliance scanning works
- [ ] Security dashboard shows metrics
- [ ] Scheduled scans work with Celery
- [ ] Metrics and alerting configured
- [ ] Performance: p95 scan time < 30s
- [ ] Complete documentation delivered

---

## Dependencies & Risks

### Critical Dependencies

| Dependency | Impact | Mitigation |
|------------|--------|------------|
| pip-audit updates | Scanner accuracy | Auto-update vulnerability DB daily |
| PostgreSQL availability | Scan storage | Retry logic, graceful degradation |
| MCP protocol | Integration | Follow spec, version negotiation |

### Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Scan timeouts | Medium | Medium | Configurable timeout, async processing |
| False positives | High | Low | Tuning, suppression mechanism |
| Performance issues | Medium | High | Caching, optimization, resource limits |
| Integration complexity | Medium | Medium | Incremental rollout, feature flags |

---

## Resource Requirements

### Personnel

| Role | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|------|---------|---------|---------|---------|
| Backend Engineer | 40h | 24h | 32h | 24h |
| Security Engineer | 22h | 34h | 12h | 38h |
| Frontend Engineer | - | - | 44h | 18h |
| DevOps Engineer | 4h | - | - | 10h |
| QA Engineer | 12h | 12h | 16h | - |
| Technical Writer | - | - | - | 16h |

### Infrastructure

- Additional container: security-scanner (256MB-512MB RAM)
- Additional database storage: ~10GB for scan results (90-day retention)
- Network: Internal blitz-net access only

---

## Milestone Schedule

| Milestone | Date | Deliverables |
|-----------|------|--------------|
| Phase 1 Complete | Week 2 | Basic scanner service working |
| Phase 2 Complete | Week 4 | Policy engine and code scanning |
| Phase 3 Complete | Week 6 | Workflow integration complete |
| Phase 4 Complete | Week 8 | Enterprise features and docs |
| v1.4 Release | Week 9 | Production deployment |

---

## Approval

**Stakeholder Sign-off:**

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Tech Lead | | | |
| Security Lead | | | |
| Product Manager | | | |
| Engineering Manager | | | |

---

*Document Version: 1.0*  
*Next Review: Weekly during implementation*
