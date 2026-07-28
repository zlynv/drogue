"""Tests for error classes."""
from __future__ import annotations

import pytest

from drogue.core.errors import (
    BackendFailure,
    BanError,
    ConfigurationError,
    DrogueError,
    RateLimitExceeded,
    StorageError,
)


class TestErrors:
    def test_drogue_error(self) -> None:
        with pytest.raises(DrogueError):
            raise DrogueError("test error")

    def test_rate_limit_exceeded(self) -> None:
        exc = RateLimitExceeded(
            retry_after=30.0,
            limit=100,
            remaining=0,
            key="user1",
        )
        assert exc.retry_after == 30.0
        assert exc.limit == 100
        assert exc.key == "user1"
        assert isinstance(exc, DrogueError)

    def test_backend_failure(self) -> None:
        original = ConnectionError("redis down")
        exc = BackendFailure(
            backend="RedisStorage",
            original_error=original,
        )
        assert exc.backend == "RedisStorage"
        assert exc.original_error is original

    def test_ban_error(self) -> None:
        exc = BanError(
            key="192.168.1.1",
            expires_at=1234567890.0,
            level=3,
        )
        assert exc.key == "192.168.1.1"
        assert exc.level == 3

    def test_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("bad config")

    def test_storage_error(self) -> None:
        with pytest.raises(StorageError):
            raise StorageError("storage failed")
