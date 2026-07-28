from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class AlgorithmType(Enum):
    """Rate limiting algorithm types."""

    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


@dataclass(frozen=True)
class RateLimitRule:
    """Defines a rate limit rule."""

    limit: int
    window: float
    algorithm: AlgorithmType = AlgorithmType.TOKEN_BUCKET

    # Scope
    scope: str = "endpoint"
    methods: list[str] | None = None
    paths: list[str] | None = None

    # Cost
    cost: int | Callable[..., Awaitable[int] | int] = 1

    # Behavior
    block: bool = False
    timeout: float | None = None
    fail_closed: bool = True

    # Response
    headers: bool = True
    retry_after: bool = True

    # Shadow mode (evaluate but don't enforce)
    shadow: bool = False

    # Exemptions
    exempt_keys: set[str] = field(default_factory=set)
    exempt_paths: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.limit < 0:
            raise ValueError(f"limit must be >= 0, got {self.limit}")
        if self.window <= 0:
            raise ValueError(f"window must be > 0, got {self.window}")


# Rate string patterns: "100/minute", "10/second", "1000/hour", "5/day"
_RATE_PATTERN = re.compile(
    r"^(?P<limit>\d+)/(?P<window>\d*)(?P<unit>second|minute|hour|day|s|m|h|d)$"
)

_WINDOW_MULTIPLIERS = {
    "second": 1.0,
    "s": 1.0,
    "minute": 60.0,
    "m": 60.0,
    "hour": 3600.0,
    "h": 3600.0,
    "day": 86400.0,
    "d": 86400.0,
}


def parse_rule_string(
    rule_str: str,
    *,
    algorithm: AlgorithmType = AlgorithmType.TOKEN_BUCKET,
    block: bool = False,
    timeout: float | None = None,
    **kwargs: Any,
) -> RateLimitRule:
    """Parse a rate limit string like '100/minute' into a RateLimitRule.

    Args:
        rule_str: Rate string in format "N/unit" (e.g., "100/minute").
        algorithm: Algorithm to use.
        block: Whether to block until allowed.
        timeout: Max wait time if blocking.
        **kwargs: Additional rule parameters.

    Returns:
        RateLimitRule instance.

    Raises:
        ValueError: If the rate string format is invalid.
    """
    match = _RATE_PATTERN.match(rule_str.strip().lower())
    if not match:
        raise ValueError(
            f"Invalid rate string: '{rule_str}'. "
            f"Expected format: 'N/unit' where unit is second/minute/hour/day."
        )

    limit = int(match.group("limit"))
    unit = match.group("unit")
    window = _WINDOW_MULTIPLIERS[unit]

    return RateLimitRule(
        limit=limit,
        window=window,
        algorithm=algorithm,
        block=block,
        timeout=timeout,
        **kwargs,
    )
