from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AcquireResult:
    """Result of a rate limit check."""

    allowed: bool
    remaining: int
    limit: int
    retry_after: float | None = None
    reset_at: float | None = None

    @property
    def headers(self) -> dict[str, str]:
        """Build standard rate limit headers."""
        headers: dict[str, str] = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
        }
        if self.reset_at is not None:
            headers["X-RateLimit-Reset"] = str(int(self.reset_at))
        if not self.allowed and self.retry_after is not None:
            headers["Retry-After"] = str(int(self.retry_after))
        return headers


class Algorithm(ABC):
    """Rate limiting algorithm interface."""

    @abstractmethod
    async def acquire(
        self,
        key: str,
        cost: int = 1,
        block: bool = False,
        timeout: float | None = None,
    ) -> AcquireResult:
        """Try to acquire rate limit tokens.

        Args:
            key: Unique identifier for the rate limit bucket.
            cost: Number of tokens to consume.
            block: If True, wait until tokens are available.
            timeout: Max seconds to wait if blocking.

        Returns:
            AcquireResult with allowed status and remaining count.
        """
        ...

    @abstractmethod
    async def peek(self, key: str) -> AcquireResult:
        """Check current state without consuming tokens."""
        ...

    @abstractmethod
    async def reset(self, key: str) -> None:
        """Reset rate limit state for a key."""
        ...


class Storage(ABC):
    """Storage backend interface for rate limit state."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the storage backend (connect, etc.)."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the storage backend."""
        ...

    @abstractmethod
    async def incr(self, key: str, window: float, amount: int = 1) -> int:
        """Increment counter in window, return new count."""
        ...

    @abstractmethod
    async def get(self, key: str) -> Any:
        """Get current value for key."""
        ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: float) -> None:
        """Set value with TTL in seconds."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete key."""
        ...

    @abstractmethod
    async def expire(self, key: str, ttl: float) -> None:
        """Set expiry on existing key."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        ...

    @abstractmethod
    async def ttl(self, key: str) -> float:
        """Get remaining TTL for key (-1 = no expiry, -2 = not found)."""
        ...

    @abstractmethod
    async def increment_by(
        self, key: str, amount: int, window: float
    ) -> tuple[int, float]:
        """Atomically increment and get (new_count, ttl_remaining).

        Returns:
            Tuple of (new_count, ttl_remaining_seconds).
        """
        ...

    @abstractmethod
    async def compare_and_swap(
        self, key: str, expected: Any, new_value: Any, ttl: float
    ) -> bool:
        """Atomically swap value only if current value matches expected.

        Returns True if swap succeeded (value was == expected).
        Returns False if swap failed (value was != expected).
        This prevents race conditions in read-modify-write patterns.
        """
        ...

    # Lua script execution for atomic operations
    async def eval_script(self, script: str, keys: list[str], args: list[str | int]) -> Any:
        """Execute a Lua script atomically (for Redis backends)."""
        raise NotImplementedError("eval_script not supported by this backend")


class IdentityExtractor(ABC):
    """Extracts rate limit key from request context."""

    @abstractmethod
    async def extract(self, context: dict[str, Any]) -> str:
        """Return unique identifier for rate limiting.

        Args:
            context: Framework-specific request context dict with keys like
                     'client.host', 'headers', 'path', 'user_id', etc.
        """
        ...

    def __add__(self, other: IdentityExtractor) -> CompositeExtractor:
        """Combine extractors: first non-anonymous wins."""
        return CompositeExtractor(self, other)

    def __or__(self, other: IdentityExtractor) -> CompositeExtractor:
        """Alias for __add__."""
        return self.__add__(other)


class CompositeExtractor(IdentityExtractor):
    """Combine multiple extractors, first non-anonymous wins."""

    def __init__(self, *extractors: IdentityExtractor) -> None:
        self.extractors = extractors

    async def extract(self, context: dict[str, Any]) -> str:
        for ext in self.extractors:
            key = await ext.extract(context)
            if key and key != "anonymous":
                return key
        return "anonymous"
