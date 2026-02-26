"""
Pydantic v2 models for structured sub-agent outputs.
These schemas are the contract between backend sub-agents and frontend A2UI components.
Phase 3 uses mock data — schemas remain identical when real data arrives in Phase 4.
CLAUDE.md: Pydantic v2 BaseModel, full type annotations.
"""
from pydantic import BaseModel


class EmailSummaryItem(BaseModel):
    from_: str
    subject: str
    received_at: str  # ISO 8601 string
    snippet: str
    is_unread: bool


class EmailSummaryOutput(BaseModel):
    agent: str = "email"
    unread_count: int
    items: list[EmailSummaryItem]


class CalendarEvent(BaseModel):
    title: str
    start_time: str  # ISO 8601 string
    end_time: str    # ISO 8601 string
    location: str | None = None
    has_conflict: bool = False


class CalendarOutput(BaseModel):
    agent: str = "calendar"
    date: str  # ISO date string "YYYY-MM-DD"
    events: list[CalendarEvent]


class ProjectStatusResult(BaseModel):
    agent: str = "project"
    project_name: str
    status: str  # "active" | "on-hold" | "completed"
    owner: str
    progress_pct: int
    last_update: str
