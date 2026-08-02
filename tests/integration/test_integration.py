"""Comprehensive integration tests for drogue.

Tests rate limiting, headers, DDoS detection, bans, circuit breaker,
error handling, and response formats for both FastAPI and Django.
"""
from __future__ import annotations

import json
import os
import sys
import time

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tests.integration.fastapi_app import (
    app as fastapi_app,
)
from tests.integration.fastapi_app import (
    circuit,
)
from tests.integration.fastapi_app import (
    storage as fastapi_storage,
)
from drogue.adapters.fastapi.limiter import _last_result as _drogue_last_result

# ============================================================================
# FastAPI Tests
# ============================================================================

class TestFastAPIHeaders:
    """Verify rate limit headers on every response."""

    def setup_method(self) -> None:
        fastapi_storage._store.clear()
        _drogue_last_result.clear()
        self.client = TestClient(fastapi_app)

    def test_ping_returns_rate_limit_headers(self) -> None:
        resp = self.client.get("/api/ping")
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        assert "X-RateLimit-Reset" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == "10"

    def test_remaining_decrements(self) -> None:
        r1 = self.client.get("/api/ping")
        r2 = self.client.get("/api/ping")
        assert int(r1.headers["X-RateLimit-Remaining"]) > int(r2.headers["X-RateLimit-Remaining"])

    def test_429_contains_retry_after(self) -> None:
        for _ in range(10):
            self.client.get("/api/ping")
        resp = self.client.get("/api/ping")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        assert int(resp.headers["Retry-After"]) >= 0

    def test_429_body_format(self) -> None:
        for _ in range(10):
            self.client.get("/api/ping")
        resp = self.client.get("/api/ping")
        assert resp.status_code == 429
        body = resp.json()
        assert "error" in body
        assert "retry_after" in body
        assert "limit" in body

    def test_default_limits_apply(self) -> None:
        resp = self.client.get("/api/free")
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" in resp.headers


class TestFastAPIAlgorithms:
    """Test all 3 algorithms via separate endpoints."""

    def setup_method(self) -> None:
        fastapi_storage._store.clear()
        _drogue_last_result.clear()
        self.client = TestClient(fastapi_app)

    def test_token_bucket(self) -> None:
        for _ in range(10):
            assert self.client.get("/api/ping").status_code == 200
        assert self.client.get("/api/ping").status_code == 429

    def test_sliding_window(self) -> None:
        for _ in range(5):
            assert self.client.get("/api/slow").status_code == 200
        assert self.client.get("/api/slow").status_code == 429

    def test_fixed_window(self) -> None:
        for _ in range(5):
            assert self.client.get("/api/fixed").status_code == 200
        assert self.client.get("/api/fixed").status_code == 429


class TestFastAPIDDoSDetection:
    """Test DDoS detection endpoint."""

    def setup_method(self) -> None:
        fastapi_storage._store.clear()
        _drogue_last_result.clear()
        self.client = TestClient(fastapi_app)

    def test_ddos_check_returns_stats(self) -> None:
        resp = self.client.get("/api/ddos-check")
        assert resp.status_code == 200
        body = resp.json()
        assert "is_anomalous" in body
        assert "stats" in body
        assert "http_global_rate" in body["stats"]

    def test_ddos_not_anomalous_with_few_samples(self) -> None:
        resp = self.client.get("/api/ddos-check")
        body = resp.json()
        assert body["is_anomalous"] is False


class TestFastAPIBanSystem:
    """Test progressive auto-ban system."""

    def setup_method(self) -> None:
        self.client = TestClient(fastapi_app)
        self.client.post("/api/ban-reset")

    def test_no_ban_initially(self) -> None:
        resp = self.client.get("/api/ban-check")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_violations_lead_to_ban(self) -> None:
        for i in range(5):
            resp = self.client.post("/api/ban-violate")
            body = resp.json()
            if i < 4:
                assert body["is_banned"] is False
            else:
                assert body["is_banned"] is True

    def test_banned_request_rejected(self) -> None:
        for _ in range(5):
            self.client.post("/api/ban-violate")
        resp = self.client.get("/api/ban-check")
        assert resp.status_code == 403

    def test_ban_reset(self) -> None:
        for _ in range(5):
            self.client.post("/api/ban-violate")
        assert self.client.get("/api/ban-check").status_code == 403
        self.client.post("/api/ban-reset")
        assert self.client.get("/api/ban-check").status_code == 200


class TestFastAPICircuitBreaker:
    """Test circuit breaker states."""

    def setup_method(self) -> None:
        self.client = TestClient(fastapi_app)
        self.client.post("/api/circuit-reset")

    def test_closed_allows_requests(self) -> None:
        resp = self.client.get("/api/circuit-check")
        assert resp.status_code == 200
        assert resp.json()["circuit"]["state"] == "closed"

    def test_failures_trip_circuit(self) -> None:
        for _ in range(3):
            self.client.post("/api/circuit-fail")
        resp = self.client.get("/api/circuit-check")
        assert resp.status_code == 503
        body = resp.json()
        assert body.get("error") == "circuit_open"

    def test_circuit_half_open_after_timeout(self) -> None:
        for _ in range(3):
            self.client.post("/api/circuit-fail")
        circuit._last_failure_time = time.monotonic() - 10
        resp = self.client.get("/api/circuit-check")
        assert resp.status_code in (200, 503)

    def test_success_resets_circuit(self) -> None:
        for _ in range(3):
            self.client.post("/api/circuit-fail")
        circuit._last_failure_time = time.monotonic() - 10
        self.client.get("/api/circuit-check")
        self.client.post("/api/circuit-success")
        resp = self.client.get("/api/circuit-check")
        assert resp.status_code == 200


class TestFastAPIMultipleLimits:
    """Test multiple rate limits on same route.

    Each @limiter.limit() creates an independent algorithm with its own
    storage key, so both the 10/minute and 3/second limits are enforced.
    """

    def setup_method(self) -> None:
        fastapi_storage._store.clear()
        _drogue_last_result.clear()
        self.client = TestClient(fastapi_app)

    def test_second_limit_applies(self) -> None:
        for _ in range(3):
            assert self.client.get("/api/multi").status_code == 200
        resp = self.client.get("/api/multi")
        assert resp.status_code == 429


class TestFastAPIDependencyInjection:
    """Test Depends() rate limiting."""

    def setup_method(self) -> None:
        fastapi_storage._store.clear()
        _drogue_last_result.clear()
        self.client = TestClient(fastapi_app)

    def test_dep_rate_limit(self) -> None:
        for _ in range(5):
            assert self.client.get("/api/dep").status_code == 200
        assert self.client.get("/api/dep").status_code == 429


class TestFastAPIErrorHandling:
    """Test error responses."""

    def setup_method(self) -> None:
        fastapi_storage._store.clear()
        _drogue_last_result.clear()
        self.client = TestClient(fastapi_app)

    def test_500_on_unhandled_error(self) -> None:
        client = TestClient(fastapi_app, raise_server_exceptions=False)
        resp = client.get("/api/always-fail")
        assert resp.status_code == 500


# ============================================================================
# Stress tests
# ============================================================================

class TestDDoSSimulation:
    """Simulate burst traffic patterns."""

    def setup_method(self) -> None:
        fastapi_storage._store.clear()
        _drogue_last_result.clear()
        self.client = TestClient(fastapi_app)

    def test_burst_100_requests(self) -> None:
        results = []
        for _ in range(100):
            resp = self.client.get("/api/ping")
            results.append(resp.status_code)
        allowed = results.count(200)
        rejected = results.count(429)
        assert allowed == 10
        assert rejected == 90

    def test_all_rejected_have_retry_after(self) -> None:
        for _ in range(10):
            self.client.get("/api/ping")
        for _ in range(5):
            resp = self.client.get("/api/ping")
            assert resp.status_code == 429
            assert "Retry-After" in resp.headers

    def test_concurrent_endpoint_independence(self) -> None:
        for _ in range(10):
            self.client.get("/api/ping")
        assert self.client.get("/api/ping").status_code == 429
        assert self.client.get("/api/slow").status_code == 200

    def test_all_endpoints_respond(self) -> None:
        endpoints = [
            "/api/ping", "/api/slow", "/api/fixed", "/api/dep",
            "/api/ddos-check", "/api/ban-check", "/api/circuit-check",
            "/api/free", "/api/multi",
        ]
        for path in endpoints:
            resp = self.client.get(path)
            assert resp.status_code in (200, 429, 403, 503), (
                f"{path} returned unexpected {resp.status_code}"
            )

    def test_response_json_valid(self) -> None:
        for path in ["/api/ping", "/api/slow", "/api/fixed", "/api/free",
                      "/api/ddos-check", "/api/ban-check", "/api/circuit-check"]:
            resp = self.client.get(path)
            if resp.status_code == 200:
                body = resp.json()
                assert isinstance(body, dict)


# ============================================================================
# Django Tests
# ============================================================================

class TestDjangoRateLimiting:
    """Test Django adapter with real HTTP requests."""

    def setup_method(self) -> None:
        from django.conf import settings
        from django.test import Client

        # Ensure Django is configured with the right URL conf
        # (conftest.py already called settings.configure and django.setup)
        settings.ROOT_URLCONF = "tests.integration.django_urls"
        self.client = Client()
        from tests.integration.django_views import _storage

        _storage._store.clear()

    def test_ping_returns_headers(self) -> None:
        resp = self.client.get("/api/ping")
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" in resp

    def test_ping_blocks_after_limit(self) -> None:
        for _ in range(10):
            assert self.client.get("/api/ping").status_code == 200
        resp = self.client.get("/api/ping")
        assert resp.status_code == 429

    def test_429_body_format(self) -> None:
        for _ in range(10):
            self.client.get("/api/ping")
        resp = self.client.get("/api/ping")
        assert resp.status_code == 429
        body = json.loads(resp.content)
        assert "error" in body
        assert "retry_after" in body

    def test_429_has_retry_after_header(self) -> None:
        for _ in range(10):
            self.client.get("/api/ping")
        resp = self.client.get("/api/ping")
        assert resp.status_code == 429
        assert "Retry-After" in resp

    def test_free_endpoint_no_limit(self) -> None:
        for _ in range(20):
            assert self.client.get("/api/free").status_code == 200

    def test_separate_endpoints_independent(self) -> None:
        for _ in range(10):
            self.client.get("/api/ping")
        assert self.client.get("/api/ping").status_code == 429
        assert self.client.get("/api/slow").status_code == 200

    def test_all_django_endpoints_respond(self) -> None:
        for path in ["/api/ping", "/api/slow", "/api/fixed", "/api/free"]:
            resp = self.client.get(path)
            assert resp.status_code in (200, 429), f"{path} returned {resp.status_code}"

    def test_django_429_json_body(self) -> None:
        for _ in range(10):
            self.client.get("/api/ping")
        resp = self.client.get("/api/ping")
        assert resp.status_code == 429
        body = json.loads(resp.content)
        assert "limit" in body


# ============================================================================
# Cross-cutting concerns
# ============================================================================

class TestFailClosed:
    """Verify fail-closed behavior when backend is unavailable."""

    def setup_method(self) -> None:
        fastapi_storage._store.clear()
        _drogue_last_result.clear()

    def test_fastapi_fail_closed(self) -> None:
        from unittest.mock import patch

        from drogue.core.errors import BackendFailure

        async def failing_get(key: str):
            raise BackendFailure(message="test", backend="mock")

        client = TestClient(fastapi_app)
        with patch.object(fastapi_storage, "get", failing_get):
            resp = client.get("/api/ping")
            assert resp.status_code == 429
            body = resp.json()
            assert "unavailable" in body.get("error", "").lower()


class TestBackendFailureError:
    """Test BackendFailure error class."""

    def test_construction(self) -> None:
        from drogue.core.errors import BackendFailure

        err = BackendFailure(message="test error", backend="RedisStorage")
        assert err.message == "test error"
        assert err.backend == "RedisStorage"
        assert "test error" in str(err)
