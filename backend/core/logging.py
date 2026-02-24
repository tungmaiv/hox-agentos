"""
Structured logging configuration for Blitz AgentOS.

All logging uses structlog for JSON output.
Never use print() or bare logging.info() in application code.
Never log credential values (access_token, refresh_token, password).
"""
import logging
import sys
from pathlib import Path

import structlog


def configure_logging(
    log_level: str = "INFO",
    audit_log_path: str = "logs/audit.jsonl",
) -> None:
    """
    Configure structlog for JSON output.

    Call once at application startup (main.py create_app()).
    """
    Path(audit_log_path).parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_audit_logger() -> structlog.stdlib.BoundLogger:
    """
    Returns the audit logger for security-sensitive events.

    Use for: tool calls, ACL decisions, credential access, auth events.
    NEVER log: access_token, refresh_token, password, or any credential value.

    Example:
        logger = get_audit_logger()
        logger.info("tool_call", tool="email.fetch", user_id=str(user_id), allowed=True)
    """
    return structlog.get_logger("audit")
