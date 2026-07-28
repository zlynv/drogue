"""Circuit breaker with jitter to prevent thundering herd.

Protects backend services by stopping requests when failure rates
are high, with random jitter to prevent all clients from retrying
simultaneously.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreaker:
    """Circuit breaker with jitter.

    States:
        CLOSED: Normal operation. Requests pass through.
                Failures are counted. When failures >= threshold, trip to OPEN.

        OPEN: All requests are rejected immediately.
             After recovery_timeout (+ jitter), transition to HALF_OPEN.

        HALF_OPEN: One test request is allowed through.
                   If it succeeds, transition to CLOSED.
                   If it fails, transition back to OPEN.

    Jitter prevents thundering herd: when the circuit opens, clients
    don't all retry at exactly the same time.

    Usage:
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
        if cb.allow_request():
            try:
                response = call_backend()
                cb.record_success()
            except Exception:
                cb.record_failure()
                raise
        else:
            return 503
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    jitter: float = 0.2
    half_open_max_calls: int = 1

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _half_open_calls: int = field(default=0, init=False)

    @property
    def state(self) -> CircuitState:
        """Current circuit state (auto-transitions from OPEN to HALF_OPEN)."""
        if self._state == CircuitState.OPEN and self._should_try_recovery():
            self._state = CircuitState.HALF_OPEN
            self._half_open_calls = 0
        return self._state

    def allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        current = self.state  # triggers auto-transition

        if current == CircuitState.CLOSED:
            return True

        if current == CircuitState.OPEN:
            return False

        # HALF_OPEN: allow limited test calls
        if self._half_open_calls < self.half_open_max_calls:
            self._half_open_calls += 1
            return True
        return False

    def record_success(self) -> None:
        """Record a successful request."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            # Successful test call — close the circuit
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self) -> None:
        """Record a failed request."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            # Test call failed — reopen the circuit
            self._state = CircuitState.OPEN
            self._half_open_calls = 0
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN

    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time,
        }

    def reset(self) -> None:
        """Manually reset the circuit to CLOSED."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0

    def _should_try_recovery(self) -> bool:
        """Check if enough time has passed to try recovery."""
        if self._last_failure_time == 0:
            return True

        elapsed = time.monotonic() - self._last_failure_time
        # Add jitter: recovery_timeout * (1 +/- jitter)
        jitter_range = self.recovery_timeout * self.jitter
        adjusted_timeout = self.recovery_timeout + random.uniform(-jitter_range, jitter_range)
        return elapsed >= adjusted_timeout
