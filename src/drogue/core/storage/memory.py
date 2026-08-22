from __future__ import annotations

import threading
import time
from typing import Any

from drogue.core.abstracts import Storage


class MemoryStorage(Storage):
    """In-memory storage backend.

    Thread-safe via RLock. Good for single-process deployments
    and development/testing.

    For production with multiple workers, use Redis instead.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float | None]] = {}  # key -> (value, expiry)
        self._lock = threading.RLock()
        self._initialized = False
        self._ops_since_cleanup = 0
        self._cleanup_interval = 100  # run cleanup every N ops

    async def initialize(self) -> None:
        self._initialized = True

    async def close(self) -> None:
        self._store.clear()
        self._initialized = False

    def _cleanup_expired(self) -> None:
        """Remove expired keys (called lazily)."""
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._store.items() if exp is not None and exp <= now]
        for k in expired:
            del self._store[k]

    def _maybe_cleanup(self) -> None:
        """Periodically clean up expired keys on write operations."""
        self._ops_since_cleanup += 1
        if self._ops_since_cleanup >= self._cleanup_interval:
            self._ops_since_cleanup = 0
            self._cleanup_expired()

    async def incr(self, key: str, window: float, amount: int = 1) -> int:
        with self._lock:
            self._maybe_cleanup()
            now = time.monotonic()
            entry = self._store.get(key)

            if entry is None or (entry[1] is not None and entry[1] <= now):
                # Key doesn't exist or expired: create new window
                new_count = amount
                self._store[key] = (new_count, now + window)
                return new_count

            value, expiry = entry
            new_count = value + amount
            self._store[key] = (new_count, expiry)
            return new_count

    async def get(self, key: str) -> Any:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expiry = entry
            if expiry is not None and expiry <= time.monotonic():
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: Any, ttl: float) -> None:
        with self._lock:
            self._maybe_cleanup()
            self._store[key] = (value, time.monotonic() + ttl)

    async def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    async def expire(self, key: str, ttl: float) -> None:
        with self._lock:
            entry = self._store.get(key)
            if entry is not None:
                value, _ = entry
                self._store[key] = (value, time.monotonic() + ttl)

    async def exists(self, key: str) -> bool:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            _, expiry = entry
            if expiry is not None and expiry <= time.monotonic():
                del self._store[key]
                return False
            return True

    async def ttl(self, key: str) -> float:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return -2.0
            _, expiry = entry
            if expiry is None:
                return -1.0
            remaining = expiry - time.monotonic()
            return max(0.0, remaining)

    async def increment_by(
        self, key: str, amount: int, window: float
    ) -> tuple[int, float]:
        with self._lock:
            self._maybe_cleanup()
            now = time.monotonic()
            entry = self._store.get(key)

            if entry is None or (entry[1] is not None and entry[1] <= now):
                new_count = amount
                new_expiry = now + window
                self._store[key] = (new_count, new_expiry)
                return new_count, window

            value, expiry = entry
            new_count = value + amount
            self._store[key] = (new_count, expiry)
            remaining = max(0.0, expiry - now)
            return new_count, remaining

    def __len__(self) -> int:
        """Number of active keys (for testing/debugging)."""
        with self._lock:
            self._cleanup_expired()
            return len(self._store)

    async def compare_and_swap(
        self, key: str, expected: Any, new_value: Any, ttl: float
    ) -> bool:
        """Atomically swap value only if current value matches expected.

        If expected is None, the swap only succeeds when the key does NOT
        exist (or is expired) — create-if-absent for race-free init.
        """
        with self._lock:
            now = time.monotonic()
            entry = self._store.get(key)

            # Treat expired entries as absent
            if entry is not None and entry[1] is not None and entry[1] <= now:
                del self._store[key]
                entry = None

            if expected is None:
                # Create-if-absent semantics
                if entry is not None:
                    return False
            else:
                if entry is None:
                    return False

                value, _ = entry
                if value != expected:
                    return False

            self._store[key] = (new_value, now + ttl)
            return True

    def __repr__(self) -> str:
        return f"MemoryStorage(keys={len(self)})"
