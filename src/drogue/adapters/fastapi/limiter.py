from __future__ import annotations

import functools
import inspect
import logging
from typing import TYPE_CHECKING, Any

from drogue.core.algorithms import (
    FixedWindowAlgorithm,
    SlidingWindowAlgorithm,
    TokenBucketAlgorithm,
)
from drogue.core.config import DrogueConfig
from drogue.core.errors import RateLimitExceeded
from drogue.core.headers import build_429_response, inject_rate_limit_headers
from drogue.core.identity import RemoteAddressExtractor
from drogue.core.rules.resolver import CostResolver
from drogue.core.rules.rule import AlgorithmType, RateLimitRule, parse_rule_string
from drogue.core.storage.memory import MemoryStorage

if TYPE_CHECKING:
    from collections.abc import Callable

    from drogue.core.abstracts import AcquireResult, Algorithm, IdentityExtractor, Storage

logger = logging.getLogger("drogue.fastapi")

_ALGORITHM_MAP: dict[AlgorithmType, type[Algorithm]] = {
    AlgorithmType.TOKEN_BUCKET: TokenBucketAlgorithm,
    AlgorithmType.SLIDING_WINDOW: SlidingWindowAlgorithm,
    AlgorithmType.FIXED_WINDOW: FixedWindowAlgorithm,
}

# Stores the last AcquireResult for each request so the middleware can inject
# the correct route-level headers.  Populated by the decorator via _find_request.
_last_result: dict[int, AcquireResult] = {}
_last_result_id: int = 0  # monotonically increasing, avoids id() reuse


class DrogueLimiter:
    """Main entry point for FastAPI rate limiting.

    Usage:
        app = FastAPI()
        limiter = DrogueLimiter(app)

        @app.get("/api/data")
        @limiter.limit("100/minute")
        async def get_data():
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
        self._app: Any = None

        # Global rules (applied to all routes via middleware)
        self._global_rules: list[RateLimitRule] = list(rules or [])

        # Parse default limits as global rules
        for limit_str in (default_limits or []):
            rule = parse_rule_string(limit_str)
            object.__setattr__(rule, "scope", "global")
            self._global_rules.append(rule)

        # CIDR filtering
        self._cidr_filter = None
        if self.config.cidr_allowlist or self.config.cidr_denylist:
            from drogue.protection.cidr import CIDRFilter
            self._cidr_filter = CIDRFilter(
                allowlist=self.config.cidr_allowlist,
                denylist=self.config.cidr_denylist,
            )

        # Adaptive rate limiting
        self._adaptive = None
        if self.config.adaptive_enabled:
            from drogue.protection.adaptive import AdaptiveRateLimiter
            self._adaptive = AdaptiveRateLimiter(
                cpu_threshold=self.config.adaptive_cpu_threshold,
                memory_threshold=self.config.adaptive_memory_threshold,
                latency_threshold=self.config.adaptive_latency_threshold,
                check_interval=self.config.adaptive_check_interval,
            )

        # Shadow mode tracking
        self._shadow_stats: dict[str, int] = {}

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Any) -> None:
        """Register middleware and exception handler with a FastAPI app."""
        try:
            from starlette.requests import Request
            from starlette.responses import JSONResponse
        except ImportError as exc:
            raise ImportError(
                "FastAPI/starlette is required for DrogueLimiter. "
                "Install with: pip install drogue[fastapi]"
            ) from exc

        self._app = app
        limiter = self

        @app.exception_handler(RateLimitExceeded)
        async def rate_limit_handler(request: Any, exc: RateLimitExceeded) -> JSONResponse:
            headers: dict[str, str] = {}
            if exc.retry_after is not None:
                headers["Retry-After"] = str(int(exc.retry_after))
            if exc.limit is not None:
                headers["X-RateLimit-Limit"] = str(exc.limit)
            if exc.remaining is not None:
                headers["X-RateLimit-Remaining"] = str(max(0, exc.remaining))
            body: dict[str, Any] = {"error": "Rate limit exceeded"}
            if exc.retry_after is not None:
                body["retry_after"] = exc.retry_after
            if exc.limit is not None:
                body["limit"] = exc.limit
            return JSONResponse(
                body,
                status_code=429,
                headers=headers,
            )

        # Pure ASGI middleware — no BaseHTTPMiddleware overhead, full control
        from starlette.datastructures import MutableHeaders
        from starlette.types import ASGIApp, Message, Receive, Scope, Send

        class DrogueASGIMiddleware:
            """ASGI middleware that enforces global rate limits and injects headers."""

            def __init__(self, app: ASGIApp) -> None:
                self.app = app

            async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                if scope["type"] != "http":
                    await self.app(scope, receive, send)
                    return

                from drogue.core.errors import BackendFailure

                request = Request(scope)
                req_id = id(scope)

                try:
                    context = _request_to_context(request)
                    key = await limiter.key_func.extract(context)

                    # Check global rules
                    global_result = None
                    for rule in limiter._global_rules:
                        global_result = await limiter._check(
                            key, rule, context, route_key="__global__"
                        )
                        if not global_result.allowed:
                            response_body = build_429_response(global_result)
                            import json
                            body = json.dumps(response_body).encode()
                            await send({
                                "type": "http.response.start",
                                "status": 429,
                                "headers": [
                                    [b"content-type", b"application/json"],
                                    [b"content-length", str(len(body)).encode()],
                                    *[
                                        [k.encode(), str(v).encode()]
                                        for k, v in (global_result.headers or {}).items()
                                    ],
                                ],
                            })
                            await send({
                                "type": "http.response.body",
                                "body": body,
                            })
                            return

                except BackendFailure:
                    import json
                    body = json.dumps({
                        "error": "Rate limit service unavailable",
                        "retry_after": 1,
                    }).encode()
                    await send({
                        "type": "http.response.start",
                        "status": 429,
                        "headers": [
                            [b"content-type", b"application/json"],
                            [b"content-length", str(len(body)).encode()],
                            [b"retry-after", b"1"],
                        ],
                    })
                    await send({
                        "type": "http.response.body",
                        "body": body,
                    })
                    return

                # Wrap send to capture response headers and inject rate-limit info
                response_started = False
                nonlocal_response_headers: MutableHeaders | None = None

                async def send_wrapper(message: Message) -> None:
                    nonlocal response_started, nonlocal_response_headers

                    if message["type"] == "http.response.start":
                        response_started = True
                        nonlocal_response_headers = MutableHeaders(scope=message)

                        # Determine which result to use for headers
                        route_result = _last_result.pop(req_id, None)
                        result_to_use = route_result or global_result
                        if result_to_use and nonlocal_response_headers is not None:
                            inject_rate_limit_headers(
                                nonlocal_response_headers, result_to_use
                            )

                    await send(message)

                await self.app(scope, receive, send_wrapper)

        app.add_middleware(DrogueASGIMiddleware)

    def _get_algorithm(self, rule: RateLimitRule, route_key: str = "") -> Algorithm:
        """Get or create algorithm instance for a rule.

        Each route gets its own algorithm instance (separate token buckets).
        """
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
        # Check CIDR filter
        if self._cidr_filter and context:
            client_ip = context.get("client", {}).get("host", "")
            if client_ip and self._cidr_filter.is_denied(client_ip):
                # Deny immediately
                from drogue.core.abstracts import AcquireResult
                return AcquireResult(
                    allowed=False,
                    limit=rule.limit,
                    remaining=0,
                    retry_after=0,
                    headers={},
                )

        # Get effective limit (adaptive)
        effective_limit = rule.limit
        if self._adaptive:
            effective_limit = self._adaptive.get_effective_limit(rule.limit)

        # Create modified rule with effective limit
        if effective_limit != rule.limit:
            rule = RateLimitRule(
                limit=effective_limit,
                window=rule.window,
                algorithm=rule.algorithm,
                scope=rule.scope,
                methods=rule.methods,
                paths=rule.paths,
                cost=rule.cost,
                block=rule.block,
                timeout=rule.timeout,
                fail_closed=rule.fail_closed,
                headers=rule.headers,
                retry_after=rule.retry_after,
                shadow=rule.shadow,
                exempt_keys=rule.exempt_keys,
                exempt_paths=rule.exempt_paths,
            )

        algo = self._get_algorithm(rule, route_key)
        cost = await CostResolver.resolve_cost(rule, context)
        # Prefix key with route_key AND rule params to ensure separate storage
        rule_id = f"{rule.algorithm.value}:{rule.limit}:{rule.window}"
        storage_key = f"{route_key}:{rule_id}:{key}" if route_key else key
        result = await algo.acquire(storage_key, cost=cost, block=rule.block, timeout=rule.timeout)

        # Shadow mode: log but don't enforce
        if rule.shadow or self.config.shadow_enabled:
            shadow_key = route_key or "global"
            self._shadow_stats[shadow_key] = self._shadow_stats.get(shadow_key, 0) + 1
            if not result.allowed:
                logger.info(
                    "shadow_mode: would have blocked key=%s route=%s retry_after=%.1f",
                    key,
                    shadow_key,
                    result.retry_after or 0,
                )
            # Always allow in shadow mode
            return AcquireResult(
                allowed=True,
                limit=result.limit,
                remaining=result.remaining,
                retry_after=0,
                headers=result.headers,
            )

        return result

    def limit(
        self,
        rule_str: str,
        *,
        algorithm: AlgorithmType = AlgorithmType.TOKEN_BUCKET,
        block: bool = False,
        timeout: float | None = None,
        key_func: IdentityExtractor | None = None,
    ) -> Callable:
        """Decorator for route-level rate limiting.

        Does NOT require `request: Request` in the function signature.

        Usage:
            @app.get("/api/data")
            @limiter.limit("100/minute")
            async def get_data():
                return {"data": "value"}
        """
        rule = parse_rule_string(rule_str, algorithm=algorithm, block=block, timeout=timeout)

        def decorator(func: Callable) -> Callable:
            func_name = f"{func.__module__}.{func.__qualname__}"
            self._route_rules.setdefault(func_name, []).append(rule)

            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                request = kwargs.pop("request", None) or _find_request(args, kwargs)
                context = _request_to_context(request) if request else {}

                extractor = key_func or self.key_func
                key = await extractor.extract(context)

                for r in self._route_rules.get(func_name, [rule]):
                    result = await self._check(key, r, context, route_key=func_name)
                    if not result.allowed:
                        raise RateLimitExceeded(
                            retry_after=result.retry_after,
                            limit=result.limit,
                            remaining=result.remaining,
                            key=key,
                        )

                # Store the result keyed by the ASGI scope id so the
                # middleware can inject the correct route-level headers.
                if request is not None and rule.headers:
                    scope = getattr(request, "scope", None)
                    if scope is not None:
                        _last_result[id(scope)] = result

                response = await func(*args, **kwargs)
                return response

            # Inject Request into wrapper's signature so FastAPI injects it
            # even when the original route function has no parameters.
            from starlette.requests import Request as _StarletteRequest

            orig_sig = inspect.signature(func)
            params = list(orig_sig.parameters.values())
            if not any(p.name == "request" for p in params):
                params.insert(
                    0,
                    inspect.Parameter(
                        "request",
                        inspect.Parameter.KEYWORD_ONLY,
                        annotation=_StarletteRequest,
                    ),
                )
            wrapper.__signature__ = inspect.Signature(
                parameters=params, return_annotation=orig_sig.return_annotation
            )

            return wrapper

        return decorator

    def dependency(
        self,
        rule_str: str,
        *,
        algorithm: AlgorithmType = AlgorithmType.TOKEN_BUCKET,
        key_func: IdentityExtractor | None = None,
    ) -> Callable:
        """Create a FastAPI dependency for rate limiting.

        Usage:
            @app.get("/api/data")
            async def get_data(_=Depends(limiter.dependency("100/minute"))):
                return {"data": "value"}
        """
        rule = parse_rule_string(rule_str, algorithm=algorithm)
        limiter_ref = self

        async def _dep(
            request: Any,
            response: Any,
        ) -> None:
            context = _request_to_context(request)
            extractor = key_func or limiter_ref.key_func
            key = await extractor.extract(context)
            route_key = f"dep:{rule_str}"

            result = await limiter_ref._check(key, rule, context, route_key=route_key)

            if not result.allowed:
                raise RateLimitExceeded(
                    retry_after=result.retry_after,
                    limit=result.limit,
                    remaining=result.remaining,
                    key=key,
                )

            if hasattr(response, "headers") and rule.headers:
                inject_rate_limit_headers(response.headers, result)

        # Use FastAPI's special parameter types
        from starlette.requests import Request
        from starlette.responses import Response
        _dep.__annotations__ = {
            "request": Request,
            "response": Response,
        }

        return _dep

    def get_shadow_stats(self) -> dict[str, int]:
        """Get shadow mode statistics (routes that would have been blocked)."""
        return dict(self._shadow_stats)

    def clear_shadow_stats(self) -> None:
        """Clear shadow mode statistics."""
        self._shadow_stats.clear()

    def get_cidr_filter(self) -> Any | None:
        """Get the CIDR filter instance, if configured."""
        return self._cidr_filter

    def get_adaptive_metrics(self) -> dict[str, Any] | None:
        """Get adaptive rate limiting metrics, if enabled."""
        if self._adaptive:
            return self._adaptive.get_metrics()
        return None

    def limit_ws(
        self,
        rule_str: str,
        *,
        algorithm: AlgorithmType = AlgorithmType.TOKEN_BUCKET,
        key_func: IdentityExtractor | None = None,
    ) -> Callable:
        """Decorator for WebSocket rate limiting."""
        rule = parse_rule_string(rule_str, algorithm=algorithm)

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(websocket: Any, *args: Any, **kwargs: Any) -> Any:
                context = _websocket_to_context(websocket)
                extractor = key_func or self.key_func
                key = await extractor.extract(context)

                result = await self._check(key, rule, context, route_key="ws")
                if not result.allowed:
                    await websocket.close(code=4008, reason="Rate limit exceeded")
                    return

                return await func(websocket, *args, **kwargs)

            return wrapper

        return decorator


def _find_request(args: tuple, kwargs: dict) -> Any:
    """Find the Request object in function arguments."""
    for arg in args:
        if hasattr(arg, "url") and hasattr(arg, "headers"):
            return arg
    for val in kwargs.values():
        if hasattr(val, "url") and hasattr(val, "headers"):
            return val
    return None


def _request_to_context(request: Any) -> dict[str, Any]:
    """Convert a Starlette Request to a context dict."""
    if request is None:
        return {}
    return {
        "client": {"host": request.client.host if request.client else "127.0.0.1"},
        "headers": dict(request.headers),
        "path": request.url.path,
        "method": request.method,
        "query_params": dict(request.query_params),
        "state": getattr(request, "state", None),
        "request": request,
    }


def _websocket_to_context(websocket: Any) -> dict[str, Any]:
    """Convert a WebSocket to a context dict."""
    if websocket is None:
        return {}
    return {
        "client": {"host": websocket.client.host if websocket.client else "127.0.0.1"},
        "headers": dict(websocket.headers),
        "path": websocket.url.path,
        "method": "WS",
        "state": getattr(websocket, "state", None),
        "request": websocket,
    }
