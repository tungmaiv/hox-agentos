"""Tests for timed() context manager in core/logging.py."""
import pytest
from unittest.mock import MagicMock
from core.logging import timed


def test_timed_logs_duration_ms():
    """timed() logs event with duration_ms after block exits."""
    mock_logger = MagicMock()

    with timed(mock_logger, "memory_search", user_id="abc"):
        pass  # instant block

    mock_logger.info.assert_called_once()
    call_kwargs = mock_logger.info.call_args
    assert call_kwargs[0][0] == "memory_search"
    assert "duration_ms" in call_kwargs[1]
    assert isinstance(call_kwargs[1]["duration_ms"], int)
    assert call_kwargs[1]["user_id"] == "abc"


def test_timed_duration_is_non_negative():
    """duration_ms is always >= 0."""
    import time
    mock_logger = MagicMock()

    with timed(mock_logger, "test_event"):
        time.sleep(0.001)

    call_kwargs = mock_logger.info.call_args
    assert call_kwargs[1]["duration_ms"] >= 1


def test_timed_logs_even_on_exception():
    """timed() logs duration_ms even when the block raises."""
    mock_logger = MagicMock()

    with pytest.raises(ValueError):
        with timed(mock_logger, "failing_op"):
            raise ValueError("boom")

    mock_logger.info.assert_called_once()
    assert "duration_ms" in mock_logger.info.call_args[1]
