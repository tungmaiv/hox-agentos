"""
Intent classifier for master agent routing.
Routes user messages to: email, calendar, project, or general.
Uses blitz/fast LLM (low-latency, simple classification task).
CLAUDE.md: get_llm() only — no direct provider imports.
"""
import structlog
from langchain_core.messages import HumanMessage

from core.config import get_llm
from core.prompts import load_prompt

logger = structlog.get_logger(__name__)

_VALID_LABELS = {"email", "calendar", "project", "general"}


async def classify_intent(message: str) -> str:
    """
    Classify user intent. Returns one of: 'email', 'calendar', 'project', 'general'.
    Never raises — invalid LLM output falls back to 'general'.
    """
    llm = get_llm("blitz/fast")
    try:
        response = await llm.ainvoke(
            [HumanMessage(content=load_prompt("intent_classifier", message=message))]
        )
        label = str(response.content).strip().lower()
        if label not in _VALID_LABELS:
            logger.warning(
                "intent_classification_invalid_label",
                label=label,
                message=message[:50],
            )
            return "general"
        return label
    except Exception as exc:
        logger.error("intent_classification_failed", error=str(exc))
        return "general"
