"""
Security Scanner Service — standalone FastAPI microservice.

Endpoints:
  GET /health  → {"status": "ok", "version": "1.0.0"}
  POST /scan   → Accepts ScanRequest, returns ScanResponse

Runs pip-audit, bandit, and detect-secrets as subprocesses concurrently.
Scoring is driven by policies/default-policies.yaml.
"""
from __future__ import annotations

import asyncio
import os

import structlog
import yaml
from fastapi import FastAPI
from pydantic import BaseModel

from scanners.code_scanner import scan_code
from scanners.dependency_scanner import scan_dependencies
from scanners.secret_scanner import scan_secrets

logger = structlog.get_logger(__name__)
app = FastAPI(title="Security Scanner", version="1.0.0")

# Load scoring policy at startup
_policy_path = os.path.join(os.path.dirname(__file__), "policies", "default-policies.yaml")
with open(_policy_path) as _f:
    _POLICY: dict = yaml.safe_load(_f)


class ScanRequest(BaseModel):
    source_code: str = ""
    requirements: str = ""
    name: str = "unknown"


class ScanResponse(BaseModel):
    scan_engine: str = "docker"
    score: int
    recommendation: str
    findings: list[dict]
    bandit_issues: list[dict]
    pip_audit_issues: list[dict]
    secrets_found: bool


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}


@app.post("/scan", response_model=ScanResponse)
async def scan(request: ScanRequest) -> ScanResponse:
    """Scan skill code and dependencies for security issues.

    Runs bandit (SAST), pip-audit (CVE), and detect-secrets concurrently.
    Computes a score 0-100 based on policy weights. Returns recommendation:
    'approve' (>= 70), 'review' (40-69), or 'reject' (< 40).
    """
    # Run all scanners concurrently for performance
    bandit_issues, pip_issues, secrets_found = await asyncio.gather(
        scan_code(request.source_code),
        scan_dependencies(request.requirements),
        scan_secrets(request.source_code),
    )

    scoring = _POLICY["scoring"]
    thresholds = _POLICY["thresholds"]
    score = 100
    findings: list[dict] = []

    # Apply bandit penalties
    for issue in bandit_issues:
        sev = issue.get("issue_severity", "LOW")
        if sev == "HIGH":
            score += scoring["bandit_high"]
            findings.append({
                "tool": "bandit",
                "severity": "HIGH",
                "message": issue.get("issue_text"),
                "line": issue.get("line_number"),
                "cwe": issue.get("issue_cwe", {}).get("id") if isinstance(issue.get("issue_cwe"), dict) else None,
            })
        elif sev == "MEDIUM":
            score += scoring["bandit_medium"]
            findings.append({
                "tool": "bandit",
                "severity": "MEDIUM",
                "message": issue.get("issue_text"),
                "line": issue.get("line_number"),
            })
        else:
            score += scoring["bandit_low"]

    # Apply pip-audit CVE penalties
    for dep in pip_issues:
        for vuln in dep.get("vulns", []):
            score += scoring["cve_high"]  # Default to HIGH penalty
            fix_versions = vuln.get("fix_versions", [])
            findings.append({
                "tool": "pip_audit",
                "cve": vuln.get("id"),
                "package": dep.get("name"),
                "installed": dep.get("version"),
                "fixed_in": fix_versions[0] if fix_versions else None,
            })

    # Apply secret detection penalty (one-time, not per-secret)
    if secrets_found:
        score += scoring["secret_detected"]
        findings.append({
            "tool": "detect_secrets",
            "severity": "CRITICAL",
            "message": "Hardcoded secret detected in source code",
        })

    # Clamp score to valid range
    score = max(0, min(100, score))

    # Determine recommendation
    if score >= thresholds["approve"]:
        recommendation = "approve"
    elif score >= thresholds["review"]:
        recommendation = "review"
    else:
        recommendation = "reject"

    logger.info(
        "scan_complete",
        name=request.name,
        score=score,
        recommendation=recommendation,
        bandit_count=len(bandit_issues),
        cve_count=sum(len(d.get("vulns", [])) for d in pip_issues),
        secrets_found=secrets_found,
    )

    return ScanResponse(
        score=score,
        recommendation=recommendation,
        findings=findings,
        bandit_issues=bandit_issues,
        pip_audit_issues=pip_issues,
        secrets_found=secrets_found,
    )
