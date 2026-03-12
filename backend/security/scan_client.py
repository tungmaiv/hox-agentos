"""
SecurityScanClient: HTTP client for Docker security scanner service with in-process fallback.

Architecture:
- Primary: POST http://security-scanner:8003/scan (Docker microservice)
- Fallback: in-process SecurityScanner (skills/security_scanner.py) on any failure

Retry policy: 2 attempts, exponential backoff 2-5s (max 20s before fallback).
"""
from __future__ import annotations

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)

_RETRYABLE = (httpx.TimeoutException, httpx.ConnectError)


class SecurityScanClient:
    """HTTP client for the Docker security scanner microservice.

    Connects to http://security-scanner:8003 (Docker internal network).
    Uses tenacity for retry: 2 attempts, exponential backoff min=2s max=5s.
    """

    def __init__(
        self,
        base_url: str = "http://security-scanner:8003",
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(min=2, max=5),
        retry=retry_if_exception_type(_RETRYABLE),
        reraise=True,
    )
    async def scan_skill(self, skill_data: dict) -> dict:
        """Send skill data to Docker scanner service.

        Args:
            skill_data: Dict with keys: name, scripts/instruction_markdown, requirements

        Returns:
            Dict with scan_engine='docker', score, recommendation, findings,
            bandit_issues, pip_audit_issues, secrets_found.

        Raises:
            httpx.TimeoutException: On timeout (triggers fallback in scan_skill_with_fallback)
            httpx.ConnectError: On connection failure (triggers fallback)
            httpx.HTTPStatusError: On non-2xx response
        """
        payload = {
            "source_code": (
                skill_data.get("scripts")
                or skill_data.get("instruction_markdown")
                or ""
            ),
            "requirements": skill_data.get("requirements", ""),
            "name": skill_data.get("name", "unknown"),
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/scan", json=payload)
            response.raise_for_status()
            result = response.json()
            result["scan_engine"] = "docker"
            return result

    async def health_check(self) -> bool:
        """Check if the Docker scanner service is healthy.

        Returns:
            True if /health returns 200, False on any error (no exception propagation).
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False


async def scan_skill_with_fallback(
    skill_data: dict,
    client: SecurityScanClient | None = None,
) -> dict:
    """Scan skill with Docker service, falling back to in-process scanner on failure.

    Args:
        skill_data: Skill data dict (name, scripts/instruction_markdown, requirements, etc.)
        client: Optional SecurityScanClient. If None, creates one from settings.

    Returns:
        Scan result dict with scan_engine='docker' or scan_engine='fallback'.
        Keys: scan_engine, score, recommendation, findings,
              bandit_issues, pip_audit_issues, secrets_found.
    """
    if client is None:
        from core.config import settings

        scanner_url = getattr(settings, "security_scanner_url", "http://security-scanner:8003")
        client = SecurityScanClient(base_url=scanner_url)

    try:
        return await client.scan_skill(skill_data)
    except Exception as exc:
        logger.warning(
            "security_scan_fallback",
            reason=str(exc),
            scan_engine="fallback",
            skill_name=skill_data.get("name", "unknown"),
        )
        from skills.security_scanner import SecurityScanner

        report = await SecurityScanner().scan(skill_data)
        return {
            "scan_engine": "fallback",
            "score": report.score,
            "recommendation": report.recommendation,
            "findings": getattr(report, "findings", []),
            "bandit_issues": [],
            "pip_audit_issues": [],
            "secrets_found": False,
        }
