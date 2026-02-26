"""
Email sub-agent node. Phase 3: returns mock data.
Schema matches real data shape — A2UI components require zero changes when OAuth is wired in Phase 4.
CLAUDE.md: get_llm() for any LLM calls; Pydantic v2; structlog; full type annotations.
"""
import structlog
from langchain_core.messages import AIMessage

from agents.state.types import BlitzState
from core.schemas.agent_outputs import EmailSummaryItem, EmailSummaryOutput

logger = structlog.get_logger(__name__)

_MOCK_EMAILS: list[EmailSummaryItem] = [
    EmailSummaryItem(
        from_="ceo@blitz.local",
        subject="Q1 OKRs Review",
        received_at="2026-02-26T09:00:00Z",
        snippet="Please review the Q1 objectives attached...",
        is_unread=True,
    ),
    EmailSummaryItem(
        from_="devops@blitz.local",
        subject="Deployment successful",
        received_at="2026-02-26T08:30:00Z",
        snippet="The production deployment completed at 08:28 UTC...",
        is_unread=True,
    ),
    EmailSummaryItem(
        from_="hr@blitz.local",
        subject="Team lunch tomorrow",
        received_at="2026-02-25T16:00:00Z",
        snippet="We're doing team lunch at noon tomorrow...",
        is_unread=False,
    ),
    EmailSummaryItem(
        from_="pm@blitz.local",
        subject="Sprint planning notes",
        received_at="2026-02-25T14:00:00Z",
        snippet="Notes from today's sprint planning session...",
        is_unread=True,
    ),
    EmailSummaryItem(
        from_="ops@blitz.local",
        subject="Infrastructure report",
        received_at="2026-02-25T10:00:00Z",
        snippet="Weekly infrastructure health report attached...",
        is_unread=False,
    ),
]


async def email_agent_node(state: BlitzState) -> dict:
    """
    Email sub-agent. Returns mock EmailSummaryOutput as JSON-encoded AIMessage.
    Phase 3 only — real Gmail/M365 OAuth wired in Phase 4.
    """
    logger.info("email_agent_invoked")
    unread_count = sum(1 for e in _MOCK_EMAILS if e.is_unread)
    output = EmailSummaryOutput(unread_count=unread_count, items=_MOCK_EMAILS)
    ai_message = AIMessage(content=output.model_dump_json())
    return {"messages": [ai_message]}
