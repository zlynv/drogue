from __future__ import annotations

import time
from typing import Protocol


class Clock(Protocol):
    """Clock interface for time operations."""

    def now(self) -> float:
        """Return current time in seconds."""
        ...


class MonotonicClock:
    """Monotonic clock (immune to system time changes)."""

    def now(self) -> float:
        return time.monotonic()


class SystemClock:
    """System clock (wall clock time)."""

    def now(self) -> float:
        return time.time()


class CachedClock:
    """Clock with cached time (for high-frequency calls)."""

    def __init__(self, cache_ttl: float = 0.001) -> None:
        self.cache_ttl = cache_ttl
        self._cached_time: float = 0.0
        self._last_update: float = 0.0

    def now(self) -> float:
        now = time.monotonic()
        if now - self._last_update >= self.cache_ttl:
            self._cached_time = now
            self._last_update = now
        return self._cached_time
