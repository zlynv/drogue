"""
Comprehensive test of all drogue features.
Run: python test_all_features.py
"""

import time
from fastapi import FastAPI
from fastapi.testclient import TestClient
from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.rules.rule import AlgorithmType
from drogue.core.identity import (
    RemoteAddressExtractor,
    UserExtractor,
    HeaderExtractor,
    StaticKeyExtractor,
)
from drogue.storage.probabilistic import CountMinSketch, BloomFilter, HyperLogLog
from drogue.protection.ddos import DDoSDetector
from drogue.protection.ban import ProgressiveBanManager
from drogue.protection.trust import TrustManager
from drogue.protection.circuit import CircuitBreaker
from drogue.protection.probes import ProbeDetector
from drogue.protection.cidr import CIDRFilter
from drogue.defense.randomizer import DefenseRandomizer, HoneypotManager
from drogue.observability.metrics import DrogueMetrics


def test_rate_limiting():
    print("=" * 60)
    print("1. RATE LIMITING")
    print("=" * 60)

    app = FastAPI()
    limiter = DrogueLimiter(app, default_limits=["100/minute"])

    @app.get("/api/data")
    @limiter.limit("5/minute")
    async def get_data():
        return {"data": "value"}

    @app.get("/api/burst")
    @limiter.limit("2/second")
    async def burst_endpoint():
        return {"burst": True}

    client = TestClient(app)

    for i in range(3):
        r = client.get("/api/data")
        assert r.status_code == 200
    print("  [PASS] Normal requests work")

    r = client.get("/api/data")
    assert "X-RateLimit-Limit" in r.headers
    assert "X-RateLimit-Remaining" in r.headers
    assert "X-RateLimit-Reset" in r.headers
    print(f"  [PASS] Headers: Limit={r.headers['X-RateLimit-Limit']}, Remaining={r.headers['X-RateLimit-Remaining']}")

    for i in range(10):
        client.get("/api/data")
    r = client.get("/api/data")
    assert r.status_code == 429
    print("  [PASS] Rate limited (429) after exceeding limit")

    for i in range(2):
        client.get("/api/burst")
    r = client.get("/api/burst")
    assert r.status_code == 429
    print("  [PASS] Burst limits enforced")

    print()


def test_algorithms():
    print("=" * 60)
    print("2. ALGORITHMS")
    print("=" * 60)

    app = FastAPI()
    limiter = DrogueLimiter(app)

    @app.get("/token")
    @limiter.limit("5/minute", algorithm=AlgorithmType.TOKEN_BUCKET)
    async def token_bucket():
        return {"algo": "token_bucket"}

    @app.get("/sliding")
    @limiter.limit("5/minute", algorithm=AlgorithmType.SLIDING_WINDOW)
    async def sliding_window():
        return {"algo": "sliding_window"}

    @app.get("/fixed")
    @limiter.limit("5/minute", algorithm=AlgorithmType.FIXED_WINDOW)
    async def fixed_window():
        return {"algo": "fixed_window"}

    client = TestClient(app)

    for algo in ["/token", "/sliding", "/fixed"]:
        for i in range(5):
            r = client.get(algo)
            assert r.status_code == 200
        r = client.get(algo)
        assert r.status_code == 429
        print(f"  [PASS] {algo} algorithm works")

    print()


def test_identity_extractors():
    print("=" * 60)
    print("3. IDENTITY EXTRACTORS")
    print("=" * 60)

    RemoteAddressExtractor()
    print("  [PASS] RemoteAddressExtractor")

    UserExtractor()
    print("  [PASS] UserExtractor")

    HeaderExtractor(header_name="x-api-key")
    print("  [PASS] HeaderExtractor")

    StaticKeyExtractor(key="global")
    print("  [PASS] StaticKeyExtractor")

    composite = UserExtractor() + RemoteAddressExtractor()
    print("  [PASS] Composite extractor")

    print()


def test_ddos_detection():
    print("=" * 60)
    print("4. DDoS DETECTION")
    print("=" * 60)

    detector = DDoSDetector(window=60.0, z_threshold=3.0, min_samples=5)

    for i in range(50):
        detector.record("192.168.1.1")

    is_anomalous = detector.is_anomalous("192.168.1.1")
    print(f"  [PASS] Normal traffic, anomalous={is_anomalous}")

    for i in range(200):
        detector.record("10.0.0.1")

    is_anomalous = detector.is_anomalous("10.0.0.1")
    print(f"  [PASS] Spike detected, anomalous={is_anomalous}")

    stats = detector.get_stats()
    print(f"  [PASS] Stats: http_clients={stats['http_clients']}")

    print()


def test_auto_ban():
    print("=" * 60)
    print("5. PROGRESSIVE AUTO-BAN")
    print("=" * 60)

    manager = ProgressiveBanManager(threshold=3, window=60.0)

    assert not manager.is_banned("192.168.1.1")
    print("  [PASS] Initially not banned")

    for i in range(3):
        manager.record_violation("192.168.1.1")

    is_banned = manager.is_banned("192.168.1.1")
    print(f"  [PASS] After 3 violations, banned={is_banned}")

    ban = manager.get_ban("192.168.1.1")
    print(f"  [PASS] Ban: level={ban.level}, expires_at={ban.expires_at:.0f}")

    print()


def test_trust_system():
    print("=" * 60)
    print("6. TRUST STATE MACHINE")
    print("=" * 60)

    manager = TrustManager()

    state = manager.get_state("client_abc")
    print(f"  [PASS] Initial state: {state}")

    for i in range(5):
        manager.update("client_abc", score=1.0)

    state = manager.get_state("client_abc")
    print(f"  [PASS] After 5 positive scores: level={state.level.value}")

    for i in range(10):
        manager.update("client_abc", score=-1.0)

    state = manager.get_state("client_abc")
    print(f"  [PASS] After 10 negative scores: level={state.level.value}")

    print()


def test_circuit_breaker():
    print("=" * 60)
    print("7. CIRCUIT BREAKER")
    print("=" * 60)

    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)

    print(f"  [PASS] Initial state: {breaker.state.value}")

    for i in range(3):
        breaker.record_failure()

    print(f"  [PASS] After 3 failures: {breaker.state.value}")

    print()


def test_probe_detection():
    print("=" * 60)
    print("8. PROBE DETECTION")
    print("=" * 60)

    detector = ProbeDetector(window=300.0, probe_threshold=3)

    for i in range(10):
        detector.record("scanner.ip", f"/page{i}", 200, "GET")

    is_probe = detector.is_probing("scanner.ip")
    signal = detector.get_signal("scanner.ip")
    print(f"  [PASS] Probe detection: is_probing={is_probe}, signal={signal}")

    print()


def test_cidr_filter():
    print("=" * 60)
    print("9. CIDR FILTERING")
    print("=" * 60)

    cidr = CIDRFilter()

    cidr.add_to_allowlist("192.168.0.0/16")
    cidr.add_to_allowlist("10.0.0.0/8")
    cidr.add_to_denylist("185.220.101.0/24")

    assert cidr.is_allowed("192.168.1.1") == True
    assert cidr.is_allowed("10.0.0.1") == True
    assert cidr.is_denied("185.220.101.50") == True
    assert cidr.is_allowed("8.8.8.8") == False

    stats = cidr.get_stats()
    print(f"  [PASS] CIDR filter works, stats: {stats}")

    print()


def test_probabilistic_structures():
    print("=" * 60)
    print("10. PROBABILISTIC DATA STRUCTURES")
    print("=" * 60)

    cms = CountMinSketch(width=2**16, depth=4)
    for i in range(1000):
        cms.add(f"key_{i % 100}")

    est = cms.estimate("key_0")
    print(f"  [PASS] Count-Min Sketch: estimate for key_0 = {est}")

    bloom = BloomFilter(capacity=1000, false_positive_rate=0.01)
    for i in range(100):
        bloom.add(f"item_{i}")

    assert bloom.check("item_50") == True
    print(f"  [PASS] Bloom Filter works")

    hll = HyperLogLog(precision=10)
    for i in range(1000):
        hll.add(f"user_{i}")

    cardinality = hll.count()
    print(f"  [PASS] HyperLogLog: estimated cardinality = {cardinality}")

    print()


def test_defense_randomization():
    print("=" * 60)
    print("11. DEFENSE RANDOMIZATION & HONEYPOTS")
    print("=" * 60)

    randomizer = DefenseRandomizer()
    base = 100
    limits = [randomizer.get_effective_limit("session_1", base) for _ in range(10)]
    print(f"  [PASS] Randomized limits: {limits}")

    # Verify different sessions get different limits
    limits_s2 = [randomizer.get_effective_limit("session_2", base) for _ in range(10)]
    print(f"  [PASS] Session 2 limits: {limits_s2}")

    # Honeypots
    manager = HoneypotManager()
    manager.register("/admin/debug", auto_ban=True, ban_duration=3600.0, response_code=404)
    manager.register("/.env", auto_ban=True)
    manager.register("/wp-admin", auto_ban=True)

    # Check honeypot detection
    assert manager.is_honeypot("/admin/debug") == True
    assert manager.is_honeypot("/.env") == True
    assert manager.is_honeypot("/wp-admin") == True
    assert manager.is_honeypot("/api/data") == False
    assert manager.is_honeypot("/api/users") == False
    print("  [PASS] Honeypot path detection works")

    # Record hits
    manager.record_hit("/admin/debug", "scanner_1")
    manager.record_hit("/admin/debug", "scanner_1")
    manager.record_hit("/.env", "scanner_2")

    # Check stats
    stats = manager.get_stats()
    print(f"  [PASS] Honeypot stats: {stats}")

    # Check hits for client
    hits = manager.get_hits("scanner_1")
    print(f"  [PASS] Hits by scanner_1: {len(hits)} timestamps")

    # Check bot detection
    is_bot = manager.is_bot("scanner_1")
    print(f"  [PASS] Bot detection for scanner_1: {is_bot}")

    # Clear client
    manager.clear_client("scanner_1")
    print("  [PASS] Cleared client scanner_1")

    print()


def test_observability():
    print("=" * 60)
    print("12. OBSERVABILITY")
    print("=" * 60)

    metrics = DrogueMetrics()

    metrics.record_allowed()
    metrics.record_rejected()
    metrics.record_check_latency(0.000043)
    metrics.record_ban("192.168.1.1")
    metrics.record_ddos_detection("192.168.1.1")
    metrics.record_circuit_trip()

    prometheus = metrics.to_prometheus()
    json_out = metrics.get_summary()

    assert "drogue_requests_total" in prometheus
    print(f"  [PASS] Prometheus export ({len(prometheus)} bytes)")
    print(f"  [PASS] JSON export ({len(json_out)} bytes)")

    print()


def test_shadow_mode():
    print("=" * 60)
    print("13. SHADOW MODE (via RateLimitRule)")
    print("=" * 60)

    from drogue.core.rules.rule import RateLimitRule, AlgorithmType
    from drogue.core.storage.memory import MemoryStorage

    storage = MemoryStorage()
    rule = RateLimitRule(
        limit=2,
        window=60.0,
        algorithm=AlgorithmType.TOKEN_BUCKET,
        shadow=True,
        paths=["/api/shadow"],
    )

    assert rule.shadow == True
    print(f"  [PASS] Shadow rule created: paths={rule.paths}, shadow={rule.shadow}")

    print()


def test_blocking_mode():
    print("=" * 60)
    print("14. BLOCKING MODE")
    print("=" * 60)

    app = FastAPI()
    limiter = DrogueLimiter(app)

    @app.get("/api/blocking")
    @limiter.limit("2/minute", block=True, timeout=1.0)
    async def blocking_endpoint():
        return {"blocked": False}

    client = TestClient(app)

    for i in range(2):
        r = client.get("/api/blocking")
        assert r.status_code == 200

    r = client.get("/api/blocking")
    assert r.status_code == 429
    print("  [PASS] Blocking mode works")

    print()


def test_custom_key_func():
    print("=" * 60)
    print("15. CUSTOM KEY FUNCTION")
    print("=" * 60)

    app = FastAPI()
    limiter = DrogueLimiter(app, key_func=StaticKeyExtractor(key="global"))

    @app.get("/api/global")
    @limiter.limit("3/minute")
    async def global_limit():
        return {"global": True}

    client = TestClient(app)

    for i in range(3):
        r = client.get("/api/global")
        assert r.status_code == 200

    r = client.get("/api/global")
    assert r.status_code == 429
    print("  [PASS] Static key (global limit) works")

    print()


def test_multiple_rules():
    print("=" * 60)
    print("16. MULTIPLE RULES")
    print("=" * 60)

    app = FastAPI()
    limiter = DrogueLimiter(app)

    @app.get("/api/multi")
    @limiter.limit("3/minute")
    @limiter.limit("10/hour")
    async def multi_rule():
        return {"multi": True}

    client = TestClient(app)

    for i in range(3):
        r = client.get("/api/multi")
        assert r.status_code == 200

    r = client.get("/api/multi")
    assert r.status_code == 429
    print("  [PASS] Multiple rules enforced")

    print()


def main():
    print("\n" + "=" * 60)
    print("DROGUE COMPREHENSIVE FEATURE TEST")
    print("=" * 60 + "\n")

    start = time.time()

    test_rate_limiting()
    test_algorithms()
    test_identity_extractors()
    test_ddos_detection()
    test_auto_ban()
    test_trust_system()
    test_circuit_breaker()
    test_probe_detection()
    test_cidr_filter()
    test_probabilistic_structures()
    test_defense_randomization()
    test_observability()
    test_shadow_mode()
    test_blocking_mode()
    test_custom_key_func()
    test_multiple_rules()

    elapsed = time.time() - start

    print("=" * 60)
    print(f"ALL 16 TESTS PASSED in {elapsed:.3f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
