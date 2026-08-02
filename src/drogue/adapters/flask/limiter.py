"""Flask rate limiting adapter.

Usage:
    from flask import Flask
    from drogue.adapters.flask import DrogueLimiter

    app = Flask(__name__)
    limiter = DrogueLimiter(app, default_limits=["100/minute"])

    @app.route("/api/data")
    @limiter.limit("10/minute")
    def get_data():
        return {"data": "value"}
"""
from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING, Any

from drogue.core.algorithms import (
    FixedWindowAlgorithm,
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
    from drogue.core.abstracts import AcquireResult, Algorithm, IdentityExtractor, Storage

logger = logging.getLogger("drogue.flask")

_ALGORITHM_MAP: dict[AlgorithmType, type[Algorithm]] = {
    AlgorithmType.TOKEN_BUCKET: TokenBucketAlgorithm,
    AlgorithmType.SLIDING_WINDOW: SlidingWindowAlgorithm,
    AlgorithmType.FIXED_WINDOW: FixedWindowAlgorithm,
}

# Key used to store pending headers in flask.g
_G_DROGUE_HEADERS = "_drogue_pending_headers"


class DrogueLimiter:
    """Main entry point for Flask rate limiting.

    Usage:
        app = Flask(__name__)
        limiter = DrogueLimiter(app, default_limits=["100/minute"])

        @app.route("/api/data")
        @limiter.limit("10/minute")
        def get_data():
            return {"data": "value"}
    """

    def __init__(
        self,
        app: Any | None = None,
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

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Any) -> None:
        """Register before_request and after_request hooks with a Flask app."""
        limiter = self

        @app.before_request
        def _check_global_rate_limit() -> Any:
            from flask import jsonify, request

            from drogue.core.errors import BackendFailure

            try:
                context = _request_to_context(request)
                key = _run_async(limiter.key_func.extract(context))

                for rule in limiter._global_rules:
                    result = limiter._check_sync(key, rule, context, route_key="__global__")
                    if not result.allowed:
                        response = jsonify(build_429_response(result))
                        response.status_code = 429
                        for header, value in result.headers.items():
                            response.headers[header] = value
                        return response

                return None

            except BackendFailure:
                response = jsonify({"error": "Rate limit service unavailable", "retry_after": 1})
                response.status_code = 429
                response.headers["Retry-After"] = "1"
                return response

        @app.after_request
        def _inject_rate_limit_headers(response: Any) -> Any:
            """Inject rate limit headers into the response.

            This runs AFTER the view function returns, so the response
            is always a proper Response object (even for dict returns).
            """
            from flask import g

            pending = getattr(g, "_drogue_pending_headers", None)
            if pending:
                for header, value in pending.items():
                    response.headers[header] = value
            return response

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
        storage_key = f"{route_key}:{key}" if route_key else key
        return await algo.acquire(storage_key, cost=cost, block=rule.block, timeout=rule.timeout)

    def _check_sync(
        self,
        key: str,
        rule: RateLimitRule,
        context: dict[str, Any] | None = None,
        route_key: str = "",
    ) -> AcquireResult:
        """Synchronous check for Flask views."""
        return _run_async(self._check(key, rule, context, route_key))

    def limit(
        self,
        rule_str: str,
        *,
        algorithm: AlgorithmType = AlgorithmType.TOKEN_BUCKET,
        block: bool = False,
        key_func: IdentityExtractor | None = None,
    ) -> Any:
        """Decorator for route-level rate limiting.

        Usage:
            @app.route("/api/data")
            @limiter.limit("10/minute")
            def get_data():
                return {"data": "value"}
        """
        rule = parse_rule_string(rule_str, algorithm=algorithm, block=block)

        def decorator(func: Any) -> Any:
            func_name = f"{func.__module__}.{func.__qualname__}"
            self._route_rules.setdefault(func_name, []).append(rule)

            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                from flask import g, jsonify, request

                context = _request_to_context(request)
                extractor = key_func or self.key_func
                key = _run_async(extractor.extract(context))

                for r in self._route_rules.get(func_name, [rule]):
                    result = self._check_sync(key, r, context, route_key=func_name)
                    if not result.allowed:
                        response = jsonify(build_429_response(result))
                        response.status_code = 429
                        for header, value in result.headers.items():
                            response.headers[header] = value
                        return response

                response = func(*args, **kwargs)

                # Store headers in flask.g for after_request to inject
                # This works for ALL response types: dicts, strings, Response objects
                if rule.headers and result is not None:
                    g._drogue_pending_headers = result.headers

                return response

            return wrapper

        return decorator


def _request_to_context(request: Any) -> dict[str, Any]:
    """Convert a Flask request to a context dict."""
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    x_real_ip = request.headers.get("X-Real-IP")

    if x_real_ip:
        client_host = x_real_ip.strip()
    elif x_forwarded_for:
        client_host = x_forwarded_for.split(",")[0].strip()
    else:
        client_host = request.remote_addr or "127.0.0.1"

    return {
        "client": {"host": client_host},
        "headers": {k.lower(): v for k, v in request.headers},
        "path": request.path,
        "method": request.method,
        "query_params": dict(request.args),
        "state": {},
        "request": request,
    }


def _run_async(coro: Any) -> Any:
    """Run an async coroutine from sync code."""
    from drogue.utils.async_utils import run_async
    return run_async(coro)
