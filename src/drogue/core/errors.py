from __future__ import annotations


class DrogueError(Exception):
    """Base exception for drogue errors."""
    pass


class RateLimitExceeded(DrogueError):  # noqa: N818
    """Raised when a rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: float | None = None,
        limit: int | None = None,
        remaining: int | None = None,
        key: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining
        self.key = key


class BackendFailure(DrogueError):  # noqa: N818
    """Raised when the storage backend fails."""

    def __init__(
        self,
        message: str = "Rate limit backend unavailable",
        backend: str | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.backend = backend
        self.original_error = original_error


class BanError(DrogueError):
    """Raised when a request is banned."""

    def __init__(
        self,
        message: str = "Request banned",
        key: str | None = None,
        expires_at: float | None = None,
        level: int = 0,
    ) -> None:
        super().__init__(message)
        self.key = key
        self.expires_at = expires_at
        self.level = level


class ConfigurationError(DrogueError):
    """Raised for invalid configuration."""
    pass


class StorageError(DrogueError):
    """Raised for storage operation failures."""
    pass
