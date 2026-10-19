from __future__ import annotations

import functools
import inspect
import logging
import math
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from drogue.core.algorithms import (
    FixedWindowAlgorithm,
    GCRAAlgorithm,
    LeakyBucketAlgorithm,
    SlidingWindowAlgorithm,
    TokenBucketAlgorithm,
)
from drogue.core.config import DrogueConfig
from drogue.core.errors import (
    ConfigurationError,
    HoneypotError,
    RateLimitExceeded,
)
from drogue.core.headers import build_429_response, inject_rate_limit_headers
from drogue.core.identity import RemoteAddressExtractor
from drogue.core.rules.resolver import CostResolver
from drogue.core.rules.rule import AlgorithmType, RateLimitRule, parse_rule_string
from drogue.core.storage.memory import MemoryStorage

if TYPE_CHECKING:
    from collections.abc import Callable

    from drogue.core.abstracts import AcquireResult, Algorithm, IdentityExtractor, Storage

try:
    from starlette.datastructures import MutableHeaders  # noqa: F401
    from starlette.requests import Request
    from starlette.responses import (
        HTMLResponse,
        JSONResponse,
        RedirectResponse,
    )
    from starlette.types import ASGIApp, Message, Receive, Scope, Send  # noqa: F401
except ImportError:  # pragma: no cover - fastapi optional extra
    Request = None  # type: ignore[assignment, misc]
    HTMLResponse = JSONResponse = RedirectResponse = None  # type: ignore[assignment, misc]

logger = logging.getLogger("drogue.fastapi")

_ALGORITHM_MAP: dict[AlgorithmType, type[Algorithm]] = {
    AlgorithmType.TOKEN_BUCKET: TokenBucketAlgorithm,
    AlgorithmType.SLIDING_WINDOW: SlidingWindowAlgorithm,
    AlgorithmType.FIXED_WINDOW: FixedWindowAlgorithm,
    AlgorithmType.GCRA: GCRAAlgorithm,
    AlgorithmType.LEAKY_BUCKET: LeakyBucketAlgorithm,
}

# Stores the AcquireResult for the current request so the middleware can
# inject route-level headers. A ContextVar is used instead of a dict keyed
# by id(scope): id() values are reused after GC, which could attach one
# user's rate-limit headers to another user's response, and aborted
# requests leaked entries. ContextVar is request-scoped and self-cleaning.
_route_result: ContextVar[AcquireResult | None] = ContextVar(
    "drogue_route_result", default=None
)


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
        pipeline: Any | None = None,
        challenge_provider: Any | None = None,
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
        self._pipeline: Any = None

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

        # Detection components (probes, trust, sentinel, honeypots) live
        # in the pipeline so there is exactly one owner per component.
        # When the user did not pass a pipeline but enabled detection
        # via config, build one automatically.
        if pipeline is None and (
            self.config.probes_enabled
            or self.config.trust_enabled
            or self.config.sentinel_enabled
            or self.config.honeypot_paths
        ):
            from drogue.defense.randomizer import HoneypotManager
            from drogue.protection.pipeline import ProtectionPipeline
            from drogue.protection.probes import ProbeDetector
            from drogue.protection.sentinel import SentinelDetector
            from drogue.protection.trust import TrustManager

            auto_honeypots = None
            if self.config.honeypot_paths:
                auto_honeypots = HoneypotManager()
                for honeypot_path in self.config.honeypot_paths:
                    auto_honeypots.register(
                        honeypot_path, auto_ban=self.config.honeypot_ban
                    )
            pipeline = ProtectionPipeline(
                probes=ProbeDetector() if self.config.probes_enabled else None,
                trust=TrustManager() if self.config.trust_enabled else None,
                sentinel=SentinelDetector() if self.config.sentinel_enabled else None,
                honeypots=auto_honeypots,
                probes_retry_after=self.config.probes_retry_after,
                trust_success_threshold=self.config.trust_success_threshold,
                sentinel_sample_rate=self.config.sentinel_sample_rate,
                sentinel_block=self.config.sentinel_block,
            )
        self._pipeline = pipeline

        # Shared aliases into the pipeline's components (None when the
        # pipeline was user-supplied without them or absent entirely).
        self._trust = getattr(pipeline, "trust", None) if pipeline else None
        self._honeypots = getattr(pipeline, "honeypots", None) if pipeline else None

        # Defense randomization is a limit modifier, not detection, so
        # the limiter owns it directly.
        self._randomizer = None
        if self.config.randomizer_enabled:
            from drogue.defense.randomizer import DefenseRandomizer
            self._randomizer = DefenseRandomizer()

        # Challenge escalation: when enabled, page denials become a
        # CAPTCHA/PoW interstitial instead of a bare 429. Managed here
        # (not in the pipeline) because it wraps the limiter's denial
        # path rather than participating in route checks.
        self._challenge_manager: Any = None
        if self.config.challenge_enabled or challenge_provider is not None:
            from drogue.challenge import ChallengeManager, TurnstileProvider

            provider = challenge_provider
            if provider is None:
                if not (
                    self.config.challenge_site_key
                    and self.config.challenge_secret
                ):
                    raise ConfigurationError(
                        "challenge requires either challenge_provider= or"
                        " config.challenge_site_key + config.challenge_secret"
                    )
                provider = TurnstileProvider(
                    site_key=self.config.challenge_site_key,
                    secret=self.config.challenge_secret,
                    action=self.config.challenge_action,
                )
            self._challenge_manager = ChallengeManager(
                provider=provider,
                storage=self.storage,
                signing_key=self.config.challenge_signing_key,
                cookie_name=self.config.challenge_cookie_name,
                cookie_ttl=self.config.challenge_cookie_ttl,
                token_ttl=self.config.challenge_token_ttl,
                failure_mode=self.config.challenge_failure_mode,
                failure_threshold=self.config.challenge_failure_threshold,
                challenge_rate_limit=self.config.challenge_rate_limit,
                challenge_rate_window=self.config.challenge_rate_window,
                verify_url=self.config.challenge_verify_url,
                ban=(getattr(pipeline, "ban", None) if pipeline else None),
                trust=(getattr(pipeline, "trust", None) if pipeline else None),
            )

        self._pipeline = pipeline

        # Shadow mode tracking
        self._shadow_stats: dict[str, int] = {}

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Any) -> None:
        """Register middleware and exception handler with a FastAPI app."""
        try:
            import starlette.responses  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "FastAPI/starlette is required for DrogueLimiter. "
                "Install with: pip install drogue[fastapi]"
            ) from exc

        self._app = app
        limiter = self

        @app.exception_handler(RateLimitExceeded)
        async def rate_limit_handler(request: Any, exc: RateLimitExceeded) -> Any:
            headers: dict[str, str] = {}
            if exc.retry_after is not None:
                # Retry-After must be a positive integer; int(0.75) is "0"
                headers["Retry-After"] = str(max(1, math.ceil(exc.retry_after)))
            if exc.limit is not None:
                headers["X-RateLimit-Limit"] = str(exc.limit)
            if exc.remaining is not None:
                headers["X-RateLimit-Remaining"] = str(max(0, exc.remaining))

            # Challenge escalation: for page traffic without a valid
            # pass cookie, deny with the interstitial instead of JSON.
            manager = limiter._challenge_manager
            if manager is not None:
                client_ip = (
                    request.client.host if request.client else "127.0.0.1"
                )
                if (
                    not manager.has_valid_pass(request.cookies, client_ip)
                    and manager.should_serve(
                        request.method, request.headers.get("accept")
                    )
                ):
                    return HTMLResponse(
                        manager.page_html(request.url.path),
                        status_code=429,
                        headers=headers,
                    )

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

        @app.exception_handler(HoneypotError)
        async def honeypot_handler(request: Any, exc: HoneypotError) -> JSONResponse:
            return JSONResponse(
                {"error": "Not found"},
                status_code=exc.response_code,
            )

        manager = limiter._challenge_manager

        async def _challenge_form(request: Request) -> dict[str, str]:
            """Parse a challenge-verify form without hard deps.

            Browsers submit plain urlencoded bodies; multipart only in
            exotic setups, where python-multipart is used if installed.
            """
            content_type = request.headers.get("content-type", "")
            if "multipart/form-data" in content_type:
                try:
                    return dict(await request.form())  # type: ignore[no-any-return]
                except AssertionError:
                    pass
            from urllib.parse import parse_qs

            body = (await request.body()).decode("utf-8", "replace")
            return {k: v[0] for k, v in parse_qs(body).items()}

        if manager is not None:

            @app.post(manager.verify_url)
            async def challenge_verify(request: Request) -> Any:
                """Verify a challenge token, then set the pass cookie."""
                client_ip = (
                    request.client.host if request.client else "127.0.0.1"
                )
                form = await _challenge_form(request)
                next_url = manager.sanitize_next(str(form.get("next", "/")))
                token = str(form.get(manager.provider.field_name, ""))

                if not await manager.allow_verify_request(client_ip):
                    return JSONResponse(
                        {"error": "Too many attempts"},
                        status_code=429,
                    )

                if manager.has_valid_pass(request.cookies, client_ip):
                    return RedirectResponse(next_url, status_code=303)

                from drogue.challenge.base import (
                    ChallengeUnavailableError,
                    ChallengeVerificationError,
                )

                try:
                    verified = await manager.verify(token, client_ip, client_ip)
                except ChallengeUnavailableError:
                    # Undecided upstream (block mode, or a custom manager
                    # that raises): never grant a pass on an outage,
                    # re-serve the check with 503 so clients retry.
                    return HTMLResponse(
                        manager.page_html(next_url),
                        status_code=503,
                    )
                except ChallengeVerificationError:
                    manager_ok = False
                else:
                    manager_ok = verified

                response = RedirectResponse(next_url, status_code=303)
                if manager_ok:
                    response.set_cookie(
                        manager.cookie_name,
                        manager.issue_pass_cookie(client_ip),
                        max_age=int(manager.cookie_ttl),
                        httponly=True,
                        samesite="lax",
                        secure=limiter.config.challenge_cookie_secure,
                    )
                else:
                    return HTMLResponse(
                        manager.page_html(next_url),
                        status_code=429,
                    )
                return response

            @app.get(manager.verify_url.rsplit("/", 1)[0] + "/challenge")
            async def challenge_page() -> HTMLResponse:
                """Manual entry point for testing/embedding checks."""
                return HTMLResponse(manager.page_html("/"))

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

                try:
                    context = _request_to_context(request)
                    key = await limiter.key_func.extract(context)
                    client_ip = context.get("client", {}).get("host", key)

                    # Pipeline check (honeypot, ban, probes, DDoS,
                    # sentinel, circuit breaker)
                    if limiter._pipeline is not None:
                        result = await limiter._pipeline.check(
                            key=key,
                            context=context,
                        )
                        if not result.allowed:
                            limiter._pipeline.record_probe(
                                client_ip,
                                context.get("path", ""),
                                result.status_code,
                                context.get("method", "GET"),
                            )
                            import json as _json
                            body = _json.dumps({
                                "error": result.reason,
                                "retry_after": result.retry_after,
                            }).encode()
                            denial_headers: list[list[bytes]] = [
                                [b"content-type", b"application/json"],
                                [b"content-length", str(len(body)).encode()],
                            ]
                            if result.retry_after:
                                denial_headers.append(
                                    [
                                        b"retry-after",
                                        str(
                                            max(1, math.ceil(result.retry_after))
                                        ).encode(),
                                    ]
                                )
                            await send({
                                "type": "http.response.start",
                                "status": result.status_code,
                                "headers": denial_headers,
                            })
                            await send({
                                "type": "http.response.body",
                                "body": body,
                            })
                            return

                    # Check global rules
                    global_result = None
                    for rule in limiter._global_rules:
                        try:
                            global_result = await limiter._check(
                                key, rule, context, route_key="__global__"
                            )
                        except HoneypotError as exc:
                            import json as _honeypot_json
                            honeypot_body = _honeypot_json.dumps({
                                "error": "Not found",
                            }).encode()
                            await send({
                                "type": "http.response.start",
                                "status": exc.response_code,
                                "headers": [
                                    [b"content-type", b"application/json"],
                                    [b"content-length", str(len(honeypot_body)).encode()],
                                ],
                            })
                            await send({
                                "type": "http.response.body",
                                "body": honeypot_body,
                            })
                            return
                        if not global_result.allowed:
                            # Challenge escalation for page traffic
                            # without a valid pass cookie: serve the
                            # interstitial instead of the JSON body.
                            if (
                                manager is not None
                                and manager.should_serve(
                                    request.method,
                                    request.headers.get("accept"),
                                )
                                and not manager.has_valid_pass(
                                    request.cookies,
                                    request.client.host
                                    if request.client
                                    else "127.0.0.1",
                                )
                            ):
                                import json as _json

                                page = manager.page_html(
                                    request.url.path
                                ).encode()
                                interstitial_headers = [
                                    [b"content-type", b"text/html; charset=utf-8"],
                                    [b"content-length", str(len(page)).encode()],
                                    [b"retry-after", b"1"],
                                ]
                                await send({
                                    "type": "http.response.start",
                                    "status": 429,
                                    "headers": interstitial_headers,
                                })
                                await send({
                                    "type": "http.response.body",
                                    "body": page,
                                })
                                return

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
                    # Honor fail_closed=False by allowing traffic through
                    if not limiter.config.default_fail_closed:
                        logger.warning(
                            "BackendFailure in middleware; failing open (fail_closed=False)"
                        )
                        await self.app(scope, receive, send)
                        return
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
                        route_result = _route_result.get()
                        result_to_use = route_result or global_result
                        if result_to_use and nonlocal_response_headers is not None:
                            inject_rate_limit_headers(
                                nonlocal_response_headers, result_to_use
                            )

                        # Feed the finished response back: probe
                        # detection sees real error rates, and trust /
                        # circuit breaker learn from successes. Denials
                        # already recorded their violation at decision
                        # time, so only successes are recorded here.
                        if limiter._pipeline is not None:
                            status = message["status"]
                            limiter._pipeline.record_probe(
                                client_ip,
                                context.get("path", ""),
                                status,
                                context.get("method", "GET"),
                            )
                            if 200 <= status < 400:
                                limiter._pipeline.record_success(key)
                            elif status >= 500:
                                limiter._pipeline.record_failure(key)

                    await send(message)

                try:
                    await self.app(scope, receive, send_wrapper)
                except Exception:
                    # The app failed without a 5xx response reaching the
                    # client; the breaker still must learn about it.
                    if limiter._pipeline is not None:
                        limiter._pipeline.record_failure(key)
                    raise

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
        # Honeypot trap paths deny before anything else (bots only)
        if self._honeypots and context:
            honeypot_path = context.get("path", "") or ""
            if honeypot_path and self._honeypots.is_honeypot(honeypot_path):
                honeypot_config = self._honeypots.record_hit(honeypot_path, key)
                if (
                    honeypot_config
                    and honeypot_config.get("auto_ban", True)
                    and self._pipeline is not None
                    and getattr(self._pipeline, "ban", None) is not None
                ):
                    self._pipeline.record_violation(key)
                raise HoneypotError(
                    path=honeypot_path,
                    key=key,
                    response_code=int((honeypot_config or {}).get("response_code", 404)),
                )

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
                )

        # Get effective limit (adaptive, trust reward, session jitter)
        effective_limit = rule.limit
        if self._adaptive:
            effective_limit = self._adaptive.get_effective_limit(rule.limit)
        if (
            self._trust is not None
            and self.config.trust_limit_multiplier != 1.0
            and self._trust.is_trusted(key)
        ):
            effective_limit = max(
                1, int(effective_limit * self.config.trust_limit_multiplier)
            )
        if self._randomizer is not None and context:
            session_id = _get_session_id(
                context, self.config.randomizer_session_header
            )
            if session_id:
                session_params = self._randomizer.get_session_params(session_id)
                effective_limit = max(
                    1,
                    int(
                        effective_limit
                        * session_params.rate_limit_multiplier
                    ),
                )

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

        # Record violation for pipeline ban tracking
        if not result.allowed and self._pipeline is not None:
            self._pipeline.record_violation(key)

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
                from drogue.core.errors import BackendFailure

                # FastAPI forwards the injected request among kwargs;
                # read it WITHOUT popping so the endpoint still gets it.
                request = kwargs.get("request") or _find_request(args, kwargs)
                context = _request_to_context(request) if request else {}

                # Endpoints that never declared `request: Request` get
                # it injected synthetically into the wrapper signature;
                # strip it again so the real function does not receive
                # an unexpected kwarg.
                call_kwargs = kwargs if _forward_request else (
                    {k: v for k, v in kwargs.items() if k != "request"}
                )
                # Positional callers of the wrapper (rare, direct tests)
                # may pass request positionally: keep them untouched.
                call_args = args

                extractor = key_func or self.key_func
                key = await extractor.extract(context)

                try:
                    # Check only THIS decorator's rule; stacked decorators
                    # compose naturally (each layer checks its own rule).
                    result = await self._check(key, rule, context, route_key=func_name)
                    if not result.allowed:
                        raise RateLimitExceeded(
                            retry_after=result.retry_after,
                            limit=result.limit,
                            remaining=result.remaining,
                            key=key,
                        )
                except BackendFailure:
                    # Honor fail_closed=False by allowing traffic through
                    # instead of surfacing an unhandled 500.
                    if not rule.fail_closed and not self.config.default_fail_closed:
                        logger.warning(
                            "BackendFailure in route %s; failing open (fail_closed=False)",
                            func_name,
                        )
                        return await func(*call_args, **call_kwargs)
                    raise

                # Store the result for the middleware to inject route-level
                # headers (request-scoped via ContextVar).
                if rule.headers:
                    _route_result.set(result)

                response = await func(*call_args, **call_kwargs)
                return response


            # Inject Request into wrapper's signature so FastAPI injects it
            # even when the original route function has no parameters.
            from starlette.requests import Request as _StarletteRequest

            orig_sig = inspect.signature(func)
            params = list(orig_sig.parameters.values())
            # Whether the endpoint itself wants the Request forwarded.
            _forward_request = any(p.name == "request" for p in params)
            if not _forward_request:
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

    def get_pipeline(self) -> Any | None:
        """Get the protection pipeline (auto-built or user-supplied)."""
        return self._pipeline

    def get_trust_manager(self) -> Any | None:
        """Get the trust manager shared with the pipeline, if any."""
        return self._trust

    def get_honeypots(self) -> Any | None:
        """Get the honeypot manager shared with the pipeline, if any."""
        return self._honeypots

    def get_randomizer(self) -> Any | None:
        """Get the defense randomizer, if enabled."""
        return self._randomizer

    def get_challenge_manager(self) -> Any | None:
        """Get the challenge manager, if challenge escalation is enabled."""
        return self._challenge_manager

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
            func_name = f"{func.__module__}.{func.__qualname__}"

            @functools.wraps(func)
            async def wrapper(websocket: Any, *args: Any, **kwargs: Any) -> Any:
                context = _websocket_to_context(websocket)
                extractor = key_func or self.key_func
                key = await extractor.extract(context)

                result = await self._check(
                    key, rule, context, route_key=f"ws:{func_name}"
                )
                if not result.allowed:
                    await websocket.close(code=4008, reason="Rate limit exceeded")
                    return

                return await func(websocket, *args, **kwargs)

            return wrapper

        return decorator


def _get_session_id(context: dict[str, Any] | None, header_name: str) -> str | None:
    """Extract a defense-randomizer session id from request headers.

    Header lookup is case-insensitive and tolerates the bytes keys
    some frameworks produce.
    """
    headers = (context or {}).get("headers", {}) or {}
    wanted = header_name.lower()
    for name, value in headers.items():
        if isinstance(name, bytes):
            try:
                name = name.decode("latin-1")
            except Exception:
                continue
        if str(name).lower() != wanted:
            continue
        if isinstance(value, bytes):
            try:
                value = value.decode("latin-1")
            except Exception:
                continue
        session_id = str(value).strip()
        return session_id or None
    return None


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
