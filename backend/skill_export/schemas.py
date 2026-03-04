"""
Schemas for skill export operations.

These are internal tracking types for the export module —
not exposed in API responses.
"""
from pydantic import BaseModel


class ExportMetadata(BaseModel):
    """Internal tracking metadata for a skill export operation."""

    skill_id: str
    skill_name: str
    exported_at: str  # ISO 8601 datetime
    format_version: str = "1.0"
