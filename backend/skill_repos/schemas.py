"""
Pydantic schemas for external skill repository management.

RepoCreate       — input for adding a new repository
RepoInfo         — output for listing/fetching repos
SkillBrowseItem  — a skill entry aggregated from all repo indexes
ImportRequest    — request body for importing a skill from a repo
ImportResponse   — result of import (with security score)
IndexSchema      — validates the agentskills-index.json format
"""
from typing import Any

from pydantic import BaseModel


class RepoCreate(BaseModel):
    """Input for registering a new external skill repository."""

    url: str  # Base URL of the repository (serves agentskills-index.json)


class RepoInfo(BaseModel):
    """Output representation of a registered repository."""

    id: str
    name: str
    url: str
    description: str | None
    is_active: bool
    last_synced_at: str | None  # ISO datetime or None
    skill_count: int


class SkillBrowseItem(BaseModel):
    """A single skill entry from a repository index, for browsing."""

    name: str
    description: str | None
    version: str | None
    repository_name: str
    repository_id: str
    metadata: dict[str, Any] | None  # author, license, category, tags, source_url
    # Convenience fields extracted from metadata for easy display
    category: str | None = None
    tags: list[str] | None = None
    license: str | None = None
    author: str | None = None
    source_url: str | None = None


class ImportRequest(BaseModel):
    """Request body for importing a skill from a registered repository."""

    repository_id: str  # UUID string
    skill_name: str


class ImportResponse(BaseModel):
    """Result of importing a skill from a repository."""

    skill_id: str
    name: str
    status: str  # "pending_review"
    security_score: int
    security_recommendation: str


class IndexSchema(BaseModel):
    """Validates the agentskills-index.json format served by remote repositories."""

    repository: dict[str, Any]  # must contain: name, description, url, version
    skills: list[dict[str, Any]]
