"""Tests for Django adapter."""
from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.test import RequestFactory, SimpleTestCase

from drogue.adapters.django.limiter import (
    DrogueMiddleware,
    DrogueRateLimiter,
    _request_to_context,
)
from drogue.core.rules.rule import AlgorithmType
from drogue.core.storage.memory import MemoryStorage


class _BaseDjangoTest(SimpleTestCase):
    """Base test class with Django RequestFactory."""

    def setUp(self) -> None:
        super().setUp()
        self.factory = RequestFactory()
        self.storage = MemoryStorage()
        self.limiter = DrogueRateLimiter(storage=self.storage)

    def _make_request(self, path: str = "/test", method: str = "GET", **kwargs: str) -> HttpRequest:
        return getattr(self.factory, method.lower())(path, **kwargs)


class TestRequestToContext(_BaseDjangoTest):
    """Test Django request → context conversion."""

    def test_basic_request_context(self) -> None:
        request = self._make_request("/api/data", method="GET", REMOTE_ADDR="10.0.0.1")
        ctx = _request_to_context(request)
        assert ctx["client"]["host"] == "10.0.0.1"
        assert ctx["path"] == "/api/data"
        assert ctx["method"] == "GET"

    def test_x_forwarded_for(self) -> None:
        request = self._make_request(
            "/api/data",
            HTTP_X_FORWARDED_FOR="203.0.113.50, 70.41.3.18",
        )
        ctx = _request_to_context(request)
        assert ctx["client"]["host"] == "203.0.113.50"

    def test_x_real_ip(self) -> None:
        request = self._make_request("/api/data", HTTP_X_REAL_IP="198.51.100.42")
        ctx = _request_to_context(request)
        assert ctx["client"]["host"] == "198.51.100.42"

    def test_x_real_ip_takes_precedence(self) -> None:
        request = self._make_request(
            "/api/data",
            HTTP_X_REAL_IP="198.51.100.42",
            HTTP_X_FORWARDED_FOR="203.0.113.50",
        )
        ctx = _request_to_context(request)
        assert ctx["client"]["host"] == "198.51.100.42"


class TestBasicRateLimiting(_BaseDjangoTest):
    """Test basic rate limiting functionality."""

    def test_limit_decorator_allows_requests(self) -> None:
        @self.limiter.limit("5/minute")
        def my_view(request: HttpRequest) -> JsonResponse:
            return JsonResponse({"ok": True})

        for _ in range(5):
            request = self._make_request()
            response = my_view(request)
            assert response.status_code == 200

    def test_limit_decorator_blocks_after_limit(self) -> None:
        @self.limiter.limit("2/minute")
        def my_view(request: HttpRequest) -> JsonResponse:
            return JsonResponse({"ok": True})

        request = self._make_request()
        assert my_view(request).status_code == 200
        assert my_view(request).status_code == 200
        response = my_view(request)
        assert response.status_code == 429

    def test_separate_endpoints_independent(self) -> None:
        @self.limiter.limit("2/minute")
        def view_a(request: HttpRequest) -> JsonResponse:
            return JsonResponse({"a": True})

        @self.limiter.limit("2/minute")
        def view_b(request: HttpRequest) -> JsonResponse:
            return JsonResponse({"b": True})

        # Exhaust view_a
        assert view_a(self._make_request()).status_code == 200
        assert view_a(self._make_request()).status_code == 200
        assert view_a(self._make_request()).status_code == 429

        # view_b should still work
        assert view_b(self._make_request()).status_code == 200

    def test_different_algorithms(self) -> None:
        for algo in [AlgorithmType.TOKEN_BUCKET, AlgorithmType.SLIDING_WINDOW, AlgorithmType.FIXED_WINDOW]:
            limiter = DrogueRateLimiter(storage=MemoryStorage())
            current_algo = algo

            @limiter.limit("2/minute", algorithm=current_algo)
            def my_view(request: HttpRequest, _algo: AlgorithmType = current_algo) -> JsonResponse:
                return JsonResponse({"algo": _algo.value})

            assert my_view(self._make_request()).status_code == 200
            assert my_view(self._make_request()).status_code == 200
            assert my_view(self._make_request()).status_code == 429


class TestMiddleware(_BaseDjangoTest):
    """Test Django middleware for global rate limiting."""

    def test_middleware_blocks_after_global_limit(self) -> None:
        limiter = DrogueRateLimiter(
            storage=self.storage,
            default_limits=["2/minute"],
        )

        def dummy_view(request: HttpRequest) -> JsonResponse:
            return JsonResponse({"ok": True})

        class FakeApp:
            def __call__(self, request: HttpRequest) -> JsonResponse:
                return dummy_view(request)

        middleware = DrogueMiddleware(FakeApp())

        # Patch _get_limiter
        import drogue.adapters.django.limiter as mod
        original = mod._get_limiter
        mod._get_limiter = lambda: limiter
        try:
            request = self._make_request("/test1")
            response = middleware.process_request(request)
            assert response is None  # allowed

            request = self._make_request("/test2")
            response = middleware.process_request(request)
            assert response is None  # allowed

            request = self._make_request("/test3")
            response = middleware.process_request(request)
            assert response is not None  # blocked
            assert response.status_code == 429
        finally:
            mod._get_limiter = original

    def test_middleware_no_limiter_passthrough(self) -> None:
        def dummy_view(request: HttpRequest) -> JsonResponse:
            return JsonResponse({"ok": True})

        class FakeApp:
            def __call__(self, request: HttpRequest) -> JsonResponse:
                return dummy_view(request)

        middleware = DrogueMiddleware(FakeApp())
        request = self._make_request()
        response = middleware.process_request(request)
        assert response is None


class TestRateLimitHeaders(_BaseDjangoTest):
    """Test rate limit headers are returned."""

    def test_headers_on_allowed_request(self) -> None:
        @self.limiter.limit("5/minute")
        def my_view(request: HttpRequest) -> JsonResponse:
            return JsonResponse({"ok": True})

        request = self._make_request()
        response = my_view(request)
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response
        assert "X-RateLimit-Remaining" in response

    def test_headers_on_rejected_request(self) -> None:
        @self.limiter.limit("1/minute")
        def my_view(request: HttpRequest) -> JsonResponse:
            return JsonResponse({"ok": True})

        assert my_view(self._make_request()).status_code == 200
        response = my_view(self._make_request())
        assert response.status_code == 429
        assert "X-RateLimit-Limit" in response
        assert "Retry-After" in response


class Test429ResponseBody(_BaseDjangoTest):
    """Test 429 response body format."""

    def test_429_json_body(self) -> None:
        @self.limiter.limit("1/minute")
        def my_view(request: HttpRequest) -> JsonResponse:
            return JsonResponse({"ok": True})

        assert my_view(self._make_request()).status_code == 200
        response = my_view(self._make_request())
        assert response.status_code == 429
        import json
        body = json.loads(response.content)
        assert "error" in body
        assert "retry_after" in body
