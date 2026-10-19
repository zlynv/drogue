"""Tests for rate limit header and body generation."""
from __future__ import annotations

from drogue.core.abstracts import AcquireResult
from drogue.core.headers import build_429_response, inject_rate_limit_headers


class _Response:
    """Minimal response stub capturing set headers."""

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}

    def __setitem__(self, key: str, value: str) -> None:
        self.headers[key] = value


class TestInjectRateLimitHeaders:
    def test_injects_standard_headers(self) -> None:
        result = AcquireResult(
            allowed=True, remaining=4, limit=5, reset_at=123.45
        )
        response = _Response()
        inject_rate_limit_headers(response, result)
        assert response.headers["X-RateLimit-Limit"] == "5"
        assert response.headers["X-RateLimit-Remaining"] == "4"
        assert response.headers["X-RateLimit-Reset"] == "123"

    def test_retry_after_on_denial(self) -> None:
        result = AcquireResult(
            allowed=False, remaining=0, limit=5, retry_after=2.5
        )
        response = _Response()
        inject_rate_limit_headers(response, result)
        assert response.headers["Retry-After"] == "3"

    def test_no_retry_after_when_not_denied(self) -> None:
        result = AcquireResult(allowed=True, remaining=4, limit=5)
        response = _Response()
        inject_rate_limit_headers(response, result)
        assert "Retry-After" not in response.headers


class TestBuild429Response:
    def test_body_contains_rate_info(self) -> None:
        result = AcquireResult(
            allowed=False, remaining=0, limit=5, retry_after=2.5
        )
        body = build_429_response(result)
        assert body["status"] == 429
        assert body["limit"] == 5
        assert body["remaining"] == 0
        assert body["retry_after"] == 2

    def test_negative_remaining_renders_zero(self) -> None:
        # GCRA-style results can carry negative remaining values; the
        # response body must never advertise a negative count.
        result = AcquireResult(
            allowed=False, remaining=-3, limit=5, retry_after=1.0
        )
        body = build_429_response(result)
        assert body["remaining"] == 0

    def test_retry_after_none_omitted(self) -> None:
        result = AcquireResult(allowed=False, remaining=0, limit=5)
        body = build_429_response(result)
        assert "retry_after" not in body
