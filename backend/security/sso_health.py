"""
SSO Health Checker — runs categorized diagnostics against saved Keycloak config.

Categories:
  - certificate: TLS cert validity (expiry, verification)
  - config: Keycloak config completeness
  - connectivity: JWKS endpoint reachability
  - performance: JWKS fetch latency

Usage:
  status = await check_sso_health()
  print(status.overall)  # "healthy" | "degraded" | "unhealthy"
"""
import ssl
import time
from datetime import datetime, timezone

import httpx
import structlog
from pydantic import BaseModel

from security.circuit_breaker import get_circuit_breaker
from security.keycloak_config import get_keycloak_config

logger = structlog.get_logger(__name__)


class CategoryCheck(BaseModel):
    """Single health category result."""

    name: str  # certificate, config, connectivity, performance
    status: str  # green, yellow, red, gray
    detail: str


class SSOHealthStatus(BaseModel):
    """Aggregated SSO health check result."""

    overall: str  # healthy, degraded, unhealthy
    categories: list[CategoryCheck]
    circuit_breaker: dict | None = None
    checked_at: datetime


async def _check_certificate(issuer_url: str, ca_cert_path: str) -> tuple[str, str]:
    """
    Check TLS certificate validity for the Keycloak host.

    Returns (status, detail) where status is green/yellow/red.
    """
    import socket

    try:
        # Extract hostname from issuer URL
        from urllib.parse import urlparse

        parsed = urlparse(issuer_url)
        hostname = parsed.hostname or ""
        port = parsed.port or 443

        # Create SSL context
        ctx = ssl.create_default_context()
        if ca_cert_path:
            ctx.load_verify_locations(ca_cert_path)

        # Connect and get cert
        conn = ctx.wrap_socket(socket.socket(), server_hostname=hostname)
        conn.settimeout(10.0)
        try:
            conn.connect((hostname, port))
            cert = conn.getpeercert()
        finally:
            conn.close()

        if not cert:
            return ("red", "No certificate returned by server")

        # Check expiry
        not_after_str = cert.get("notAfter", "")
        if not_after_str:
            # Format: 'Mar 15 12:00:00 2026 GMT'
            not_after = datetime.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z")
            not_after = not_after.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            days_remaining = (not_after - now).days

            if days_remaining < 0:
                return ("red", f"Certificate expired {abs(days_remaining)} days ago")
            elif days_remaining < 7:
                return ("red", f"Certificate expires in {days_remaining} days")
            elif days_remaining < 30:
                return ("yellow", f"Certificate expires in {days_remaining} days")
            else:
                return ("green", f"Certificate valid ({days_remaining} days remaining)")

        return ("green", "Certificate valid")

    except ssl.SSLCertVerificationError as exc:
        return ("red", f"TLS certificate verification failed: {exc}")
    except Exception as exc:
        return ("red", f"Certificate check failed: {exc}")


async def _fetch_jwks_with_timing(
    jwks_url: str, ca_cert_path: str
) -> tuple[httpx.Response, float]:
    """Fetch JWKS and return (response, latency_seconds)."""
    ssl_verify: str | bool = ca_cert_path or True
    start = time.monotonic()
    async with httpx.AsyncClient(verify=ssl_verify, timeout=10.0) as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
    latency = time.monotonic() - start
    return resp, latency


async def check_sso_health() -> SSOHealthStatus:
    """Run all 4 category checks and return aggregated status."""
    cb = get_circuit_breaker()
    kc = await get_keycloak_config()

    categories: list[CategoryCheck] = []

    # 1. Config check
    if kc is None:
        categories.append(
            CategoryCheck(
                name="config",
                status="red",
                detail="No Keycloak configuration found",
            )
        )
        # If no config, other checks are not applicable
        categories.append(
            CategoryCheck(name="certificate", status="gray", detail="Not applicable — no config")
        )
        categories.append(
            CategoryCheck(name="connectivity", status="gray", detail="Not applicable — no config")
        )
        categories.append(
            CategoryCheck(name="performance", status="gray", detail="Not applicable — no config")
        )
        return SSOHealthStatus(
            overall="unhealthy",
            categories=categories,
            circuit_breaker=cb.get_state(),
            checked_at=datetime.now(timezone.utc),
        )

    # Config exists — check completeness
    missing_fields: list[str] = []
    if not kc.issuer_url:
        missing_fields.append("issuer_url")
    if not kc.client_id:
        missing_fields.append("client_id")
    if not kc.client_secret:
        missing_fields.append("client_secret")
    if not kc.realm:
        missing_fields.append("realm")

    if missing_fields:
        categories.append(
            CategoryCheck(
                name="config",
                status="red",
                detail=f"Missing fields: {', '.join(missing_fields)}",
            )
        )
    elif not kc.enabled:
        categories.append(
            CategoryCheck(
                name="config",
                status="yellow",
                detail="SSO is configured but disabled",
            )
        )
    else:
        categories.append(
            CategoryCheck(name="config", status="green", detail="Configuration complete")
        )

    # 2. Certificate check
    cert_status, cert_detail = await _check_certificate(
        kc.issuer_url, kc.ca_cert_path
    )
    categories.append(
        CategoryCheck(name="certificate", status=cert_status, detail=cert_detail)
    )

    # 3. Connectivity + 4. Performance
    try:
        resp, latency = await _fetch_jwks_with_timing(kc.jwks_url, kc.ca_cert_path)
        keys_found = len(resp.json().get("keys", []))

        # Connectivity
        categories.append(
            CategoryCheck(
                name="connectivity",
                status="green",
                detail=f"JWKS endpoint reachable ({keys_found} keys found)",
            )
        )

        # Performance
        if latency > 5.0:
            perf_status = "red"
        elif latency > 2.0:
            perf_status = "yellow"
        else:
            perf_status = "green"
        categories.append(
            CategoryCheck(
                name="performance",
                status=perf_status,
                detail=f"JWKS fetch latency: {latency:.1f}s",
            )
        )

    except Exception as exc:
        error_msg = str(exc)
        categories.append(
            CategoryCheck(
                name="connectivity",
                status="red",
                detail=f"JWKS endpoint unreachable: {error_msg}",
            )
        )
        categories.append(
            CategoryCheck(
                name="performance",
                status="gray",
                detail="Not measurable — connectivity failed",
            )
        )

    # Determine overall status
    statuses = [c.status for c in categories]
    if "red" in statuses:
        overall = "unhealthy"
    elif "yellow" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    return SSOHealthStatus(
        overall=overall,
        categories=categories,
        circuit_breaker=cb.get_state(),
        checked_at=datetime.now(timezone.utc),
    )
