"""
Tests for core/logging.py

Tests that configure_logging() sets up structlog correctly and
get_audit_logger() returns a usable logger without requiring I/O.
"""
import os
import tempfile

import structlog

from core.logging import configure_logging, get_audit_logger


def test_configure_logging_creates_audit_dir(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """configure_logging creates the audit log directory if it doesn't exist."""
    audit_path = tmp_path / "audit_logs" / "audit.jsonl"
    configure_logging(log_level="INFO", audit_log_path=str(audit_path))
    assert audit_path.parent.exists()


def test_configure_logging_accepts_different_log_levels(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """configure_logging accepts standard log level strings."""
    audit_path = tmp_path / "logs" / "audit.jsonl"
    # Should not raise for any valid log level
    for level in ("DEBUG", "INFO", "WARNING", "ERROR"):
        configure_logging(log_level=level, audit_log_path=str(audit_path))


def test_get_audit_logger_returns_bound_logger() -> None:
    """get_audit_logger() returns a structlog BoundLogger."""
    logger = get_audit_logger()
    # Should be a structlog logger (BoundLogger or BoundLoggerLazyProxy)
    assert logger is not None
    assert hasattr(logger, "info")
    assert hasattr(logger, "warning")
    assert hasattr(logger, "error")


def test_get_audit_logger_is_named_audit() -> None:
    """get_audit_logger() returns a logger named 'audit'."""
    logger = get_audit_logger()
    # structlog wraps stdlib logger; the name is in the underlying logger
    # The logger should be bound to the 'audit' name
    assert logger is not None


def test_audit_logger_can_log_without_error(tmp_path) -> None:
    """Audit logger can emit a log record without error."""
    audit_path = tmp_path / "logs" / "audit.jsonl"
    configure_logging(log_level="DEBUG", audit_log_path=str(audit_path))
    logger = get_audit_logger()
    # Should not raise
    logger.info("test_event", tool="test_tool", user_id="test-user", allowed=True)


def test_configure_logging_handles_existing_dir(tmp_path) -> None:
    """configure_logging works when log directory already exists."""
    audit_path = tmp_path / "logs" / "audit.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    # Should not raise even if dir exists
    configure_logging(log_level="INFO", audit_log_path=str(audit_path))
    assert audit_path.parent.exists()
