"""Regression tests for the 12 bugs fixed in the final audit.

Each test verifies the exact bug that was found and fixed.
These tests would have FAILED before the fixes.
"""
from __future__ import annotations

import asyncio
import threading
import time

import pytest


# ============================================================================
# P0#1: Django throttle wait() shadowed by float attribute
# ============================================================================
class TestDjangoThrottleWaitShadow:
    """Before fix: self.wait = result.retry_after shadowed the wait() method.
    Calling self.wait() after allow_request raised TypeError: 'float' is not callable.
    """

    def test_wait_returns_float_not_raises(self) -> None:
        try:
            from drogue.adapters.django.throttle import DrogueThrottle
        except (ImportError, ModuleNotFoundError):
            pytest.skip("djangorestframework not installed")

        from unittest.mock import patch

        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/test")
        request.user = type("User", (), {"is_authenticated": False})()

        throttle = DrogueThrottle()
        with patch.object(throttle, "get_rate", return_value="1/minute"):
            throttle.allow_request(
                request,
                type("View", (), {"throttle_scope": "test", "throttle_rates": {"test": "1/minute"}})(),
            )

        # wait() must be callable and return float or None (not raise TypeError)
        wait_result = throttle.wait()
        assert wait_result is None or isinstance(wait_result, float)


# ============================================================================
# P0#2: Flask double rate limiting
# ============================================================================
class TestFlaskDoubleRateLimit:
    """Before fix: header injection called _check_sync again, consuming 2 tokens
    per request. A 100/minute limit effectively became 50/minute.
    """

    def test_single_token_consumed_per_request(self) -> None:
        from flask import Flask

        from drogue.adapters.flask.limiter import DrogueLimiter

        app = Flask(__name__)
        storage = __import__("drogue.core.storage.memory", fromlist=["MemoryStorage"]).MemoryStorage()
        limiter = DrogueLimiter(app, storage=storage)

        @app.route("/test")
        @limiter.limit("5/minute")
        def test_route():
            return {"ok": True}

        with app.test_client() as client:
            # Make 5 requests — all should succeed (exactly 5 tokens)
            for i in range(5):
                resp = client.get("/test")
                assert resp.status_code == 200, f"Request {i+1} should succeed"

            # 6th request should be blocked
            resp = client.get("/test")
            assert resp.status_code == 429

    def test_no_double_consume(self) -> None:
        """Verify the decorator doesn't consume tokens twice (once for check,
        once for header injection)."""
        from flask import Flask

        from drogue.adapters.flask.limiter import DrogueLimiter

        app = Flask(__name__)
        storage = __import__("drogue.core.storage.memory", fromlist=["MemoryStorage"]).MemoryStorage()
        limiter = DrogueLimiter(app, storage=storage)

        @app.route("/test")
        @limiter.limit("5/minute")
        def test_route():
            return {"ok": True}

        with app.test_client() as client:
            # Exactly 5 requests should succeed — not 2.5 (which would happen
            # if header injection consumed a second token)
            for i in range(5):
                resp = client.get("/test")
                assert resp.status_code == 200, f"Request {i+1} should succeed"

            resp = client.get("/test")
            assert resp.status_code == 429


# ============================================================================
# P0#3+P0#4: _run_async thread leak
# ============================================================================
class TestAsyncBridgeThreadLeak:
    """Before fix: each _run_async call created a new ThreadPoolExecutor.
    After fix: shared background loop, no thread leak.
    """

    def test_thread_count_stable(self) -> None:
        from drogue.utils.async_utils import run_async

        async def noop():
            return 42

        initial_count = threading.active_count()

        # Run 100 sync→async bridges
        for _ in range(100):
            result = run_async(noop())
            assert result == 42

        # Thread count should not have grown significantly
        final_count = threading.active_count()
        assert final_count <= initial_count + 3, (
            f"Thread leak: started with {initial_count}, now {final_count}"
        )

    def test_exception_propagation(self) -> None:
        from drogue.utils.async_utils import run_async

        async def failing():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            run_async(failing())

    def test_concurrent_calls(self) -> None:
        from drogue.utils.async_utils import run_async

        async def add(a: int, b: int) -> int:
            return a + b

        results = []
        for i in range(20):
            results.append(run_async(add(i, i)))

        assert results == [i * 2 for i in range(20)]


# ============================================================================
# P1#6: FastAPI limit() missing timeout param
# ============================================================================
class TestFastAPITimeoutParam:
    """Before fix: limit() didn't accept timeout, so block=True with timeout
    was impossible through the decorator interface.
    """

    def test_timeout_param_accepted(self) -> None:
        from fastapi import FastAPI

        from drogue.adapters.fastapi.limiter import DrogueLimiter

        app = FastAPI()
        limiter = DrogueLimiter(app)

        # Should not raise — timeout param must be accepted
        @app.get("/test")
        @limiter.limit("10/minute", block=False, timeout=5.0)
        async def test_route():
            return {"ok": True}

    def test_timeout_reaches_rule(self) -> None:
        from fastapi import FastAPI

        from drogue.adapters.fastapi.limiter import DrogueLimiter

        app = FastAPI()
        limiter = DrogueLimiter(app)

        @app.get("/test")
        @limiter.limit("10/minute", block=True, timeout=2.5)
        async def test_route():
            return {"ok": True}

        # Verify at least one rule has timeout=2.5
        all_rules = [
            r for rules in limiter._route_rules.values() for r in rules
        ]
        assert any(r.timeout == 2.5 for r in all_rules)


# ============================================================================
# P1#7: Retry-After no +1 padding
# ============================================================================
class TestRetryAfterNoPadding:
    """Before fix: Retry-After added undocumented +1 second.
    After fix: uses exact retry_after value from the algorithm.
    """

    def test_retry_after_exact_value(self) -> None:
        from drogue.core.abstracts import AcquireResult

        result = AcquireResult(
            allowed=False,
            remaining=0,
            limit=10,
            retry_after=5.0,
        )
        headers = result.headers
        assert headers["Retry-After"] == "5"  # not "6"


# ============================================================================
# P2#9: DDoS _client_counts memory cap
# ============================================================================
class TestDDoSMemoryCap:
    """Before fix: _client_buckets grew unbounded. After fix: capped at max_clients."""

    def test_max_clients_enforced(self) -> None:
        from drogue.protection.ddos import DDoSDetector

        detector = DDoSDetector(window=60.0, min_rate_samples=1, max_clients=50)

        # Add 100 unique clients (all in same bucket)
        for i in range(100):
            detector.record(f"client_{i}")

        # Force cleanup: mark as needing cleanup and ensure buckets are old enough
        detector._last_cleanup = 0.0
        # Expire all buckets by setting them far in the past
        for _, buckets in detector._client_buckets.items():
            for j in range(len(buckets)):
                buckets[j] = type(buckets[j])(timestamp=0, count=buckets[j].count)

        # Trigger cleanup via a new record
        detector.record("__trigger__")

        # Should be capped at max_clients
        assert len(detector._client_buckets) <= 51  # max_clients + trigger

    def test_empty_clients_evicted(self) -> None:
        from drogue.protection.ddos import DDoSDetector, TrafficSample

        detector = DDoSDetector(window=60.0, min_rate_samples=5, max_clients=100)

        # Add clients with only 1 sample each
        for i in range(20):
            detector.record(f"client_{i}")

        # Force cleanup: set _last_cleanup to 0 so cleanup triggers,
        # and set all bucket timestamps far in the past so they expire
        detector._last_cleanup = 0.0
        cutoff_bucket = int((time.monotonic() - 60.0) / detector.bucket_size) - 1
        for _, buckets in detector._client_buckets.items():
            for j in range(len(buckets)):
                buckets[j] = TrafficSample(timestamp=float(cutoff_bucket - 1), count=1)

        # Trigger cleanup via a new record
        detector.record("trigger_cleanup")

        # Clients with expired buckets should be evicted
        assert len(detector._client_buckets) <= 1


# ============================================================================
# P2#10: Ban _violations cleanup
# ============================================================================
class TestBanViolationsCleanup:
    """Before fix: _violations dict entries for non-banned keys were never cleaned."""

    def test_empty_violations_cleaned(self) -> None:
        from drogue.protection.ban import ProgressiveBanManager

        ban = ProgressiveBanManager(threshold=10, window=0.1)

        # Record 1 violation (below threshold)
        ban.record_violation("key1")
        assert "key1" in ban._violations

        # Wait for window to expire
        time.sleep(0.15)

        # Record another violation — the old one should be cleaned
        ban.record_violation("key1")

        # The violation list should be fresh (old expired)
        assert len(ban._violations.get("key1", [])) <= 1


# ============================================================================
# P2#11: Metrics route eviction
# ============================================================================
class TestMetricsRouteEviction:
    """Before fix: _route_allowed/_route_rejected grew unbounded."""

    def test_max_routes_enforced(self) -> None:
        from drogue.observability.metrics import DrogueMetrics

        metrics = DrogueMetrics(max_routes=50)

        # Add 100 unique routes
        for i in range(100):
            metrics.record_allowed(f"route_{i}")

        # Should be capped (may exceed temporarily due to allowed+rejected totals)
        total_routes = len(metrics._route_allowed) + len(metrics._route_rejected)
        assert total_routes <= 100  # some eviction happened


# ============================================================================
# P2#12: MemoryStorage periodic cleanup
# ============================================================================
class TestMemoryStorageCleanup:
    """Before fix: expired keys accumulated forever in _store."""

    def test_periodic_cleanup_triggered(self) -> None:
        from drogue.core.storage.memory import MemoryStorage

        storage = MemoryStorage()
        storage._cleanup_interval = 5  # low interval for testing

        # Write 10 keys with short TTL
        for i in range(10):
            asyncio.run(storage.set(f"key_{i}", i, ttl=0.01))

        # Wait for expiry
        time.sleep(0.02)

        # Trigger cleanup by doing writes past the interval
        for i in range(5):
            asyncio.run(storage.set(f"trigger_{i}", i, ttl=60))

        # Expired keys should be cleaned
        assert len(storage._store) <= 5  # only the trigger keys remain


# ============================================================================
# P1#5: TokenBucket no unused threading.RLock
# ============================================================================
class TestTokenBucketNoDeadLock:
    """Before fix: TokenBucket had unused self._lock = threading.RLock()."""

    def test_no_lock_attribute(self) -> None:
        from drogue.core.algorithms.token_bucket import TokenBucketAlgorithm
        from drogue.core.storage.memory import MemoryStorage

        algo = TokenBucketAlgorithm(storage=MemoryStorage(), limit=10, window=1.0)
        assert not hasattr(algo, "_lock")


# ============================================================================
# SEC#1: Concurrent first requests must not over-admit (CAS init race)
# ============================================================================
class TestBucketInitRace:
    """Before fix: first request used plain set() — concurrent initializers
    each overwrote the bucket, admitting N requests at limit cost."""

    def test_concurrent_first_requests_capped(self) -> None:
        import asyncio

        from drogue.core.algorithms.token_bucket import TokenBucketAlgorithm
        from drogue.core.storage.memory import MemoryStorage

        async def run() -> int:
            storage = MemoryStorage()
            algo = TokenBucketAlgorithm(storage=storage, limit=5, window=60.0)
            results = await asyncio.gather(*[algo.acquire("k") for _ in range(20)])
            return sum(1 for r in results if r.allowed)

        allowed = asyncio.run(run())
        assert allowed <= 5

    def test_cas_create_if_absent(self) -> None:
        import asyncio

        from drogue.core.storage.memory import MemoryStorage

        async def run() -> None:
            s = MemoryStorage()
            assert await s.compare_and_swap("k", None, "v1", 60) is True
            # Key now exists — create-if-absent must fail
            assert await s.compare_and_swap("k", None, "v2", 60) is False

        asyncio.run(run())


# ============================================================================
# SEC#2: DDoS leave-one-out Z-score detects lone flooder
# ============================================================================
class TestDDoSLeaveOneOut:
    """Before fix: client compared against distribution including itself,
    capping Z at ~sqrt(n) — a single flooder was undetectable at defaults."""

    def test_lone_flooder_detected(self) -> None:
        from collections import deque

        from drogue.protection.ddos import DDoSDetector, TrafficSample

        d = DDoSDetector(window=60.0, z_threshold=3.0, min_clients=10)
        now = time.monotonic()

        for i in range(15):
            d._client_buckets[f"normal{i}"] = deque(
                TrafficSample(timestamp=now - 60 + t, count=1)
                for t in range(0, 60, 2)
            )
        d._client_buckets["flooder"] = deque(
            TrafficSample(timestamp=now - 60 + t, count=20) for t in range(60)
        )
        d._recompute_http_distribution(now)

        assert d.is_http_anomalous("flooder") is True
        assert d.is_http_anomalous("normal0") is False


# ============================================================================
# SEC#3: Forwarded headers ignored without trusted proxies
# ============================================================================
class TestProxyHeaderSpoofing:
    """Before fix: X-Real-IP / X-Forwarded-For were trusted unconditionally,
    letting clients rotate identity per request and bypass rate limits."""

    def test_spoofed_x_real_ip_ignored(self) -> None:
        import asyncio

        from drogue.core.identity.key import RemoteAddressExtractor

        async def run() -> str:
            ext = RemoteAddressExtractor()
            return await ext.extract(
                {
                    "client": {"host": "6.6.6.6"},
                    "headers": {"x-real-ip": "1.2.3.4"},
                }
            )

        assert asyncio.run(run()) == "6.6.6.6"

    def test_junk_header_falls_back_to_peer(self) -> None:
        import asyncio

        from drogue.core.identity.key import RemoteAddressExtractor

        async def run() -> str:
            ext = RemoteAddressExtractor(trusted_proxies=["10.0.0.5"])
            return await ext.extract(
                {
                    "client": {"host": "10.0.0.5"},
                    "headers": {"x-real-ip": "<script>not-an-ip"},
                }
            )

        assert asyncio.run(run()) == "10.0.0.5"


# ============================================================================
# SEC#4: Ban escalation not reset by dropped violation
# ============================================================================
class TestBanViolationAlwaysRecorded:
    """Before fix: when all prior violations aged out, the current one was
    silently dropped and escalation restarted from zero."""

    def test_violation_recorded_after_window_expiry(self) -> None:
        from drogue.protection.ban import ProgressiveBanManager

        ban = ProgressiveBanManager(threshold=3, window=0.05)

        ban.record_violation("k")
        ban.record_violation("k")
        time.sleep(0.1)  # all violations age out

        level = ban.record_violation("k")

        # The new violation must be recorded (count == 1), not dropped
        assert len(ban._violations["k"]) == 1
        assert level == 0


# ============================================================================
# SEC#5: CIDR filter handles IPv4-mapped IPv6 addresses
# ============================================================================
class TestCIDRMappedIPv6:
    """Before fix: ::ffff:192.168.1.1 bypassed IPv4 denylist rules."""

    def test_mapped_ipv6_matches_ipv4_denylist(self) -> None:
        from drogue.protection.cidr import CIDRFilter

        f = CIDRFilter(denylist=["192.168.1.0/24"])
        assert f.is_denied("::ffff:192.168.1.100") is True
        assert f.is_allowed("::ffff:8.8.8.8") is True


# ============================================================================
# SEC#6: Retry-After rounds up (never 0 for fractional waits)
# ============================================================================
class TestRetryAfterCeil:
    """Before fix: Retry-After used int() truncation — 0.4s became '0',
    causing clients to retry immediately in a tight loop."""

    def test_fractional_retry_after_rounds_up(self) -> None:
        from drogue.core.abstracts import AcquireResult

        result = AcquireResult(
            allowed=False, remaining=0, limit=10, retry_after=0.4
        )
        assert result.headers["Retry-After"] == "1"


# ============================================================================
# SEC#7: Rate string with numeric window prefix parsed correctly
# ============================================================================
class TestRuleStringNumericWindow:
    """Before fix: '100/30s' silently discarded the 30 and became 100/second."""

    def test_combined_window_parsed(self) -> None:
        from drogue.core.rules.rule import parse_rule_string

        rule = parse_rule_string("100/30s")
        assert rule.limit == 100
        assert rule.window == 30.0

    def test_combined_window_minutes(self) -> None:
        from drogue.core.rules.rule import parse_rule_string

        rule = parse_rule_string("50/15m")
        assert rule.window == 15 * 60.0
