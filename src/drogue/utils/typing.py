from __future__ import annotations

from typing import Any, TypeVar, overload

T = TypeVar("T")


@overload
def ensure_int(value: Any) -> int: ...


@overload
def ensure_int(value: Any, default: int) -> int: ...


def ensure_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def make_key_prefix(*parts: str) -> str:
    """Build a Redis-safe key prefix from parts."""
    return ":".join(str(p).replace(":", "_") for p in parts if p)
