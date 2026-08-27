from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils.deprecation import MiddlewareMixin

from drogue.core.algorithms import (
    FixedWindowAlgorithm,
    GCRAAlgorithm,
    LeakyBucketAlgorithm,
    SlidingWindowAlgorithm,
    TokenBucketAlgorithm,
)
from drogue.core.config import DrogueConfig
from drogue.core.headers import build_429_response
from drogue.core.identity import RemoteAddressExtractor
from drogue.core.rules.resolver import CostResolver
from drogue.core.rules.rule import AlgorithmType, RateLimitRule, parse_rule_string
from drogue.core.storage.memory import MemoryStorage

if TYPE_CHECKING:
    from collections.abc import Callable

    from drogue.core.abstracts import AcquireResult, Algorithm, IdentityExtractor, Storage

logger = logging.getLogger("drogue.django")

_ALGORITHM_MAP: dict[AlgorithmType, type[Algorithm]] = {
    AlgorithmType.TOKEN_BUCKET: TokenBucketAlgorithm,
    AlgorithmType.SLIDING_WINDOW: SlidingWindowAlgorithm,
    AlgorithmType.FIXED_WINDOW: FixedWindowAlgorithm,
    AlgorithmType.GCRA: GCRAAlgorithm,
    AlgorithmType.LEAKY_BUCKET: LeakyBucketAlgorithm,
}

# Thread-local storage for limiter instance
_local: Any = None
try:
    import threading
    _local = threading.local()
except ImportError:
    pass


def _get_limiter() -> DrogueRateLimiter:
    """Get the current limiter instance from thread-local or settings."""
    if _local is not None and hasattr(_local, "limiter"):
        return _local.limiter
    return getattr(settings, "DROGUE_LIMITER", None)  # type: ignore[no-any-return]


class DrogueRateLimiter:
    """Main entry point for Django rate limiting.

    Usage (in settings.py):
        DROGUE_LIMITER = DrogueRateLimiter(default_limits=["100/minute"])

    Usage (in views.py):
        from drogue.django import ratelimit

        @ratelimit("100/minute")
        def my_view(request):
            return JsonResponse({"data": "value"})
    """

    def __init__(
        self,
        *,
        rules: list[RateLimitRule] | None = None,
        storage: Storage | None = None,
        key_func: IdentityExtractor | None = None,
        config: DrogueConfig | None = None,
        default_limits: list[str] | None = None,
    ) -> None:
        self.config = config or DrogueConfig()
        self.storage = storage if storage is not None else MemoryStorage()
        self.key_func = key_func or RemoteAddressExtractor(
            trusted_proxies=self.config.trusted_proxies,
            trust_x_real_ip=self.config.trust_x_real_ip,
        )
        self._algorithms: dict[str, Algorithm] = {}
        self._route_rules: dict[str, list[RateLimitRule]] = {}
        self._initialized = False

        # Global rules
        self._global_rules: list[RateLimitRule] = list(rules or [])
        for limit_str in (default_limits or []):
            rule = parse_rule_string(limit_str)
            object.__setattr__(rule, "scope", "global")
            self._global_rules.append(rule)

    def initialize(self) -> None:
        """Initialize storage backend. Call once at startup."""
        _run_async(self.storage.initialize())
        self._initialized = True

    def _get_algorithm(self, rule: RateLimitRule, route_key: str = "") -> Algorithm:
        """Get or create algorithm instance for a rule."""
        algo_class = _ALGORITHM_MAP[rule.algorithm]
        cache_key = f"{route_key}:{rule.algorithm.value}:{rule.limit}:{rule.window}"
        if cache_key not in self._algorithms:
            self._algorithms[cache_key] = algo_class(
                storage=self.storage,
                limit=rule.limit,
                window=rule.window,
            )
        return self._algorithms[cache_key]

    async def _check(
        self,
        key: str,
        rule: RateLimitRule,
        context: dict[str, Any] | None = None,
        route_key: str = "",
    ) -> AcquireResult:
        """Check a single rate limit rule."""
        algo = self._get_algorithm(rule, route_key)
        cost = await CostResolver.resolve_cost(rule, context)
        # Include rule params in the storage key so multiple rules on the
        # same route get separate buckets (mirrors the FastAPI adapter).
        rule_id = f"{rule.algorithm.value}:{rule.limit}:{rule.window}"
        storage_key = f"{route_key}:{rule_id}:{key}" if route_key else key
        return await algo.acquire(storage_key, cost=cost, block=rule.block, timeout=rule.timeout)

    def _check_sync(
        self,
        key: str,
        rule: RateLimitRule,
        context: dict[str, Any] | None = None,
        route_key: str = "",
    ) -> AcquireResult:
        """Synchronous check (for Django views)."""
        from drogue.utils.async_utils import run_async

        return run_async(self._check(key, rule, context, route_key))

    def limit(
        self,
        rule_str: str,
        *,
        algorithm: AlgorithmType = AlgorithmType.TOKEN_BUCKET,
        block: bool = False,
        key_func: IdentityExtractor | None = None,
    ) -> Callable:
        """Decorator for view-level rate limiting.

        Usage:
            @ratelimit("100/minute")
            def my_view(request):
                return JsonResponse({"data": "value"})
        """
        rule = parse_rule_string(rule_str, algorithm=algorithm, block=block)

        def decorator(view_func: Callable) -> Callable:
            func_name = f"{view_func.__module__}.{view_func.__qualname__}"
            self._route_rules.setdefault(func_name, []).append(rule)

            @functools.wraps(view_func)
            def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
                context = _request_to_context(request)
                extractor = key_func or self.key_func
                key = _run_async(extractor.extract(context))

                for r in self._route_rules.get(func_name, [rule]):
                    result = self._check_sync(key, r, context, route_key=func_name)
                    if not result.allowed:
                        return JsonResponse(
                            build_429_response(result),
                            status=429,
                            headers=result.headers,
                        )

                response = view_func(request, *args, **kwargs)

                # Inject headers from the first check result
                if hasattr(response, "items") and rule.headers:
                    for header, value in result.headers.items():
                        response[header] = value

                return response

            return wrapper

        return decorator


class DrogueMiddleware(MiddlewareMixin):
    """Django middleware for global rate limiting.

    Add to MIDDLEWARE in settings.py:
        MIDDLEWARE = [
            ...
            'drogue.django.middleware.DrogueMiddleware',
        ]
    """

    def process_request(self, request: HttpRequest) -> JsonResponse | None:
        from drogue.core.errors import BackendFailure

        limiter = _get_limiter()
        if limiter is None:
            return None

        try:
            context = _request_to_context(request)
            key = _run_async(limiter.key_func.extract(context))

            for rule in limiter._global_rules:
                result = limiter._check_sync(key, rule, context, route_key="__global__")
                if not result.allowed:
                    return JsonResponse(
                        build_429_response(result),
                        status=429,
                        headers=result.headers,
                    )

            return None

        except BackendFailure:
            # Honor fail_closed=False by allowing traffic through
            if limiter.config is not None and not limiter.config.default_fail_closed:
                logger.warning(
                    "BackendFailure in middleware; failing open (fail_closed=False)"
                )
                return None
            # Fail-closed: deny request when backend is unavailable
            return JsonResponse(
                {"error": "Rate limit service unavailable", "retry_after": 1},
                status=429,
                headers={"Retry-After": "1"},
            )


def _request_to_context(request: HttpRequest) -> dict[str, Any]:
    """Convert a Django HttpRequest to a context dict.

    client.host is always REMOTE_ADDR (the direct peer). Forwarded headers
    are passed through in "headers" but only trusted by the identity
    extractor when the peer is a configured trusted proxy.
    """
    return {
        "client": {"host": request.META.get("REMOTE_ADDR", "127.0.0.1")},
        "headers": {k.lower().replace("http_", ""): v for k, v in request.META.items() if k.startswith("HTTP_")},
        "path": request.path,
        "method": request.method,
        "query_params": dict(request.GET),
        "state": getattr(request, "_drogue_state", {}),
        "request": request,
    }


def _run_async(coro: Any) -> Any:
    """Run an async coroutine from sync code."""
    from drogue.utils.async_utils import run_async
    return run_async(coro)
