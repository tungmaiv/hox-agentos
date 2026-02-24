"""
Health check route — no authentication required.

GET /health → 200 HealthResponse

This route is intentionally outside the /api prefix and requires no JWT,
so load balancers and Docker health checks can reach it without credentials.
"""
from fastapi import APIRouter

from core.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service health status. No authentication required."""
    return HealthResponse(status="ok")
