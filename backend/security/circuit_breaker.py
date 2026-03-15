"""
SSO Circuit Breaker — prevents cascading failures when Keycloak is down.

States:
  CLOSED   — normal operation, requests pass through
  OPEN     — Keycloak is down, new SSO logins blocked
  HALF_OPEN — recovery probe allowed (1 request), success closes circuit

Thresholds (configurable):
  failure_threshold     — consecutive failures before opening (default 5)
  recovery_timeout_seconds — seconds before OPEN -> HALF_OPEN (default 60)
  half_open_max_calls   — probes allowed in HALF_OPEN (default 1)

Thread safety: asyncio.Lock guards all state mutations.

Usage:
  cb = get_circuit_breaker()
  if await cb.is_open():
      raise HTTPException(503, "SSO temporarily unavailable")
  try:
      jwks = await fetch_jwks()
      await cb.record_success()
  except Exception:
      await cb.record_failure("JWKS fetch failed")
"""
import asyncio
import enum
import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class CircuitState(enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class SSOCircuitBreaker:
    """In-memory circuit breaker for SSO/Keycloak operations."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls: int = 0
        self._lock: asyncio.Lock = asyncio.Lock()
        self._callbacks: list[Callable[[str, str, str], Awaitable[None]]] = []

        # Configurable thresholds
        self.failure_threshold: int = failure_threshold
        self.recovery_timeout_seconds: float = recovery_timeout_seconds
        self.half_open_max_calls: int = half_open_max_calls

    @property
    def state(self) -> CircuitState:
        return self._state

    def register_transition_callback(
        self, callback: Callable[[str, str, str], Awaitable[None]]
    ) -> None:
        """Register a callback for state transitions: (old_state, new_state, reason)."""
        self._callbacks.append(callback)

    async def _notify_transition(
        self, old_state: str, new_state: str, reason: str
    ) -> None:
        for cb in self._callbacks:
            try:
                await cb(old_state, new_state, reason)
            except Exception as exc:
                logger.warning(
                    "circuit_breaker_callback_error",
                    error=str(exc),
                    old_state=old_state,
                    new_state=new_state,
                )

    async def record_failure(self, reason: str = "") -> None:
        """Record a failure. May transition CLOSED->OPEN or HALF_OPEN->OPEN."""
        async with self._lock:
            old_state = self._state.value
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
                logger.warning(
                    "circuit_breaker_reopened",
                    reason=reason,
                    failure_count=self._failure_count,
                )
                await self._notify_transition(old_state, self._state.value, reason)

            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self.failure_threshold
            ):
                self._state = CircuitState.OPEN
                logger.warning(
                    "circuit_breaker_opened",
                    reason=reason,
                    failure_count=self._failure_count,
                    threshold=self.failure_threshold,
                )
                await self._notify_transition(old_state, self._state.value, reason)

    async def record_success(self) -> None:
        """Record a success. May transition HALF_OPEN->CLOSED. Resets failure count."""
        async with self._lock:
            old_state = self._state.value

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._half_open_calls = 0
                logger.info("circuit_breaker_closed", note="Recovery probe succeeded")
                await self._notify_transition(
                    old_state, self._state.value, "Recovery probe succeeded"
                )
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    async def is_open(self) -> bool:
        """
        Check if circuit is open (blocking new SSO logins).

        Side effect: transitions OPEN->HALF_OPEN when recovery timeout has elapsed.
        Returns False when CLOSED or HALF_OPEN (probe allowed).
        """
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return False

            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self.recovery_timeout_seconds:
                    old_state = self._state.value
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info(
                        "circuit_breaker_half_open",
                        elapsed_seconds=round(elapsed, 1),
                    )
                    await self._notify_transition(
                        old_state,
                        self._state.value,
                        f"Recovery timeout elapsed ({round(elapsed, 1)}s)",
                    )
                    return False
                return True

            # HALF_OPEN — allow probe(s) up to max
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return False
            return True

    def get_state(self) -> dict[str, Any]:
        """Return current state as a serializable dict."""
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "last_failure_time": self._last_failure_time if self._last_failure_time else None,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_seconds": self.recovery_timeout_seconds,
            "half_open_max_calls": self.half_open_max_calls,
        }

    def reset(self) -> None:
        """Manually reset to CLOSED state (admin override)."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        self._last_failure_time = 0.0
        logger.info("circuit_breaker_manually_reset")

    def update_thresholds(
        self,
        failure_threshold: int | None = None,
        recovery_timeout_seconds: float | None = None,
        half_open_max_calls: int | None = None,
    ) -> None:
        """Update thresholds without resetting state."""
        if failure_threshold is not None:
            self.failure_threshold = failure_threshold
        if recovery_timeout_seconds is not None:
            self.recovery_timeout_seconds = recovery_timeout_seconds
        if half_open_max_calls is not None:
            self.half_open_max_calls = half_open_max_calls
        logger.info(
            "circuit_breaker_thresholds_updated",
            failure_threshold=self.failure_threshold,
            recovery_timeout=self.recovery_timeout_seconds,
            half_open_max_calls=self.half_open_max_calls,
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_circuit_breaker: SSOCircuitBreaker | None = None


def get_circuit_breaker() -> SSOCircuitBreaker:
    """Return the module-level singleton circuit breaker."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = SSOCircuitBreaker()
    return _circuit_breaker
