"""Django REST Framework throttle adapter using drogue.

Provides DrogueThrottle that plugs into DRF's throttling system,
using drogue's algorithms instead of DRF's built-in throttling.

Usage in settings.py:
    REST_FRAMEWORK = {
        'DEFAULT_THROTTLE_CLASSES': ['drogue.adapters.django.throttle.DrogueThrottle'],
        'DEFAULT_THROTTLE_RATES': {
            'user': '100/hour',
            'anon': '20/minute',
        }
    }

Usage per-view:
    from drogue.adapters.django.throttle import DrogueThrottle

    class MyView(APIView):
        throttle_classes = [DrogueThrottle]
        throttle_scope = 'user'
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.conf import settings
from rest_framework.throttling import BaseThrottle

from drogue.core.algorithms import (
    FixedWindowAlgorithm,
    GCRAAlgorithm,
    LeakyBucketAlgorithm,
    SlidingWindowAlgorithm,
    TokenBucketAlgorithm,
)
from drogue.core.rules.rule import AlgorithmType, parse_rule_string
from drogue.core.storage.memory import MemoryStorage

if TYPE_CHECKING:
    from drogue.core.abstracts import Algorithm

_ALGORITHM_MAP: dict[AlgorithmType, type[Algorithm]] = {
    AlgorithmType.TOKEN_BUCKET: TokenBucketAlgorithm,
    AlgorithmType.SLIDING_WINDOW: SlidingWindowAlgorithm,
    AlgorithmType.FIXED_WINDOW: FixedWindowAlgorithm,
    AlgorithmType.GCRA: GCRAAlgorithm,
    AlgorithmType.LEAKY_BUCKET: LeakyBucketAlgorithm,
}

# Shared storage and algorithms across throttle instances
_storage: MemoryStorage | None = None
_algorithms: dict[str, Algorithm] = {}
_MAX_ALGORITHMS = 256


def _get_storage() -> MemoryStorage:
    global _storage
    if _storage is None:
        _storage = MemoryStorage()
    return _storage


def _get_algorithm(rule_str: str, route_key: str = "") -> Algorithm:
    cache_key = f"{route_key}:{rule_str}"
    if cache_key not in _algorithms:
        if len(_algorithms) >= _MAX_ALGORITHMS:
            _algorithms.clear()
        rule = parse_rule_string(rule_str)
        algo_class = _ALGORITHM_MAP[rule.algorithm]
        _algorithms[cache_key] = algo_class(
            storage=_get_storage(),
            limit=rule.limit,
            window=rule.window,
        )
    return _algorithms[cache_key]


class DrogueThrottle(BaseThrottle):
    """DRF throttle using drogue's rate limiting algorithms.

    Configure rate via DRF's DEFAULT_THROTTLE_RATES or per-view:
        throttle_scope = 'user'
        throttle_rates = {'user': '100/hour'}

    Supports:
        - Per-user rate limiting (authenticated users)
        - Per-IP rate limiting (anonymous users)
        - All drogue algorithms (token_bucket, sliding_window, fixed_window)
    """

    def allow_request(self, request: Any, view: Any) -> bool:
        """Check if the request should be allowed."""
        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True

        # Get rate from view or global settings
        rate = self.get_rate(view)
        if rate is None:
            return True

        algo = _get_algorithm(rate, route_key=f"drf:{getattr(view, 'throttle_scope', 'default')}")

        # Run async acquire synchronously
        from drogue.utils.async_utils import run_async
        result = run_async(algo.acquire(self.key))

        self._wait_after = result.retry_after
        return result.allowed

    def get_rate(self, view: Any) -> str | None:
        """Get the throttle rate for the current view."""
        # Check view-level throttle_rates first
        throttle_rates = getattr(view, "throttle_rates", None)
        scope = getattr(view, "throttle_scope", None)

        if throttle_rates and scope and scope in throttle_rates:
            return throttle_rates[scope]

        # Fall back to DRF global settings
        rates = getattr(settings, "REST_FRAMEWORK", {}).get("DEFAULT_THROTTLE_RATES", {})
        if scope and scope in rates:
            return rates[scope]

        return None

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        """Generate cache key for the request."""
        if request.user and request.user.is_authenticated:
            return f"throttle:user:{request.user.pk}"
        return f"throttle:ip:{self.get_ident(request)}"

    def wait(self) -> float | None:  # type: ignore[override]
        """Seconds to wait before next request, or None if allowed."""
        return getattr(self, "_wait_after", None)
