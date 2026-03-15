"""
Tests for SSO circuit breaker — Plan 26-01.

Covers:
  - Initial CLOSED state
  - Transition to OPEN after consecutive failures
  - HALF_OPEN after recovery timeout
  - Recovery to CLOSED on success in HALF_OPEN
  - Re-open on failure in HALF_OPEN
  - Custom thresholds
  - get_state() returns full state dict
  - Transition callback invocation
"""
import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from security.circuit_breaker import (
    CircuitState,
    SSOCircuitBreaker,
    get_circuit_breaker,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cb(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    half_open_max_calls: int = 1,
) -> SSOCircuitBreaker:
    return SSOCircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout_seconds=recovery_timeout,
        half_open_max_calls=half_open_max_calls,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_starts_closed() -> None:
    cb = _make_cb()
    assert cb.state == CircuitState.CLOSED
    assert not await cb.is_open()


@pytest.mark.asyncio
async def test_opens_after_threshold_failures() -> None:
    cb = _make_cb(failure_threshold=5)
    for _ in range(5):
        await cb.record_failure("test-reason")
    assert cb.state == CircuitState.OPEN
    assert await cb.is_open()


@pytest.mark.asyncio
async def test_half_open_after_recovery_timeout() -> None:
    cb = _make_cb(failure_threshold=2, recovery_timeout=0.1)
    await cb.record_failure("f1")
    await cb.record_failure("f2")
    assert cb.state == CircuitState.OPEN

    # Wait for recovery timeout
    await asyncio.sleep(0.15)

    # is_open should transition to HALF_OPEN and return False (allow probe)
    assert not await cb.is_open()
    assert cb.state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_half_open_success_closes() -> None:
    cb = _make_cb(failure_threshold=2, recovery_timeout=0.05)
    await cb.record_failure("f1")
    await cb.record_failure("f2")
    await asyncio.sleep(0.1)
    await cb.is_open()  # triggers HALF_OPEN
    assert cb.state == CircuitState.HALF_OPEN

    await cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb._failure_count == 0


@pytest.mark.asyncio
async def test_half_open_failure_reopens() -> None:
    cb = _make_cb(failure_threshold=2, recovery_timeout=0.05)
    await cb.record_failure("f1")
    await cb.record_failure("f2")
    await asyncio.sleep(0.1)
    await cb.is_open()
    assert cb.state == CircuitState.HALF_OPEN

    await cb.record_failure("half-open-fail")
    assert cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_success_in_closed_resets_failure_count() -> None:
    cb = _make_cb(failure_threshold=5)
    await cb.record_failure("f1")
    await cb.record_failure("f2")
    assert cb._failure_count == 2

    await cb.record_success()
    assert cb._failure_count == 0
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_custom_thresholds() -> None:
    cb = _make_cb(failure_threshold=3, recovery_timeout=30.0)
    for _ in range(3):
        await cb.record_failure("custom")
    assert cb.state == CircuitState.OPEN

    # Should still be OPEN (30s timeout not elapsed)
    assert await cb.is_open()


@pytest.mark.asyncio
async def test_get_state_returns_dict() -> None:
    cb = _make_cb(failure_threshold=5, recovery_timeout=60.0)
    await cb.record_failure("reason-1")

    state = cb.get_state()
    assert state["state"] == "CLOSED"
    assert state["failure_count"] == 1
    assert state["failure_threshold"] == 5
    assert state["recovery_timeout_seconds"] == 60.0
    assert state["half_open_max_calls"] == 1
    assert "last_failure_time" in state


@pytest.mark.asyncio
async def test_transition_callback_invoked() -> None:
    cb = _make_cb(failure_threshold=2)
    callback = AsyncMock()
    cb.register_transition_callback(callback)

    await cb.record_failure("f1")
    await cb.record_failure("f2")

    callback.assert_called_once_with("CLOSED", "OPEN", "f2")


@pytest.mark.asyncio
async def test_get_circuit_breaker_returns_singleton() -> None:
    cb1 = get_circuit_breaker()
    cb2 = get_circuit_breaker()
    assert cb1 is cb2
