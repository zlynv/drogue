from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from drogue.core.abstracts import AcquireResult


class Response(Protocol):
    """Protocol for objects that support header setting."""

    def __setitem__(self, key: str, value: str) -> None: ...


def inject_rate_limit_headers(
    response: Response,
    result: AcquireResult,
    *,
    prefix: str = "X-RateLimit",
) -> None:
    """Inject standard rate limit headers into a response.

    Headers:
        X-RateLimit-Limit: Maximum requests per window
        X-RateLimit-Remaining: Requests remaining in current window
        X-RateLimit-Reset: Unix timestamp when window resets
        Retry-After: Seconds until next allowed request (only on 429)
    """
    response[f"{prefix}-Limit"] = str(result.limit)
    response[f"{prefix}-Remaining"] = str(max(0, result.remaining))

    if result.reset_at is not None:
        response[f"{prefix}-Reset"] = str(int(result.reset_at))

    if not result.allowed and result.retry_after is not None:
        response["Retry-After"] = str(int(result.retry_after))


def build_429_response(
    result: AcquireResult,
    *,
    message: str = "Rate limit exceeded",
    prefix: str = "X-RateLimit",
) -> dict[str, Any]:
    """Build a 429 response body with rate limit info."""
    body: dict[str, Any] = {
        "error": message,
        "status": 429,
    }
    if result.retry_after is not None:
        body["retry_after"] = int(result.retry_after)
    if result.limit:
        body["limit"] = result.limit
    if result.remaining is not None:
        body["remaining"] = result.remaining
    return body
