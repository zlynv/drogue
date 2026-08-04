"""Tests for protection layer — DDoS, ban, circuit breaker."""
from __future__ import annotations

import time

from drogue.protection.ban import ProgressiveBanManager
from drogue.protection.circuit import CircuitBreaker, CircuitState
from drogue.protection.ddos import DDoSDetector


class TestDDoSDetector:
    """Test Z-score anomaly detection."""

    def test_record_and_rate(self) -> None:
        det = DDoSDetector(window=60.0, bucket_size=0.1, min_rate_samples=1)
        for _ in range(10):
            det.record("client1")
        rate = det.get_client_rate("client1")
        assert rate > 0

    def test_not_anomalous_with_few_clients(self) -> None:
        det = DDoSDetector(min_clients=10, min_rate_samples=1)
        det.record("attacker")
        assert det.is_anomalous("attacker") is False

    def test_not_anomalous_single_client(self) -> None:
        det = DDoSDetector(min_clients=10, min_rate_samples=1, bucket_size=0.1)
        for _ in range(100):
            det.record("attacker")
        det._maybe_recompute(time.monotonic())
        assert det.is_anomalous("attacker") is False

    def test_detects_high_rate_client(self) -> None:
        det = DDoSDetector(
            window=60.0, bucket_size=0.1, min_clients=3,
            min_rate_samples=1, z_threshold=2.0, recompute_interval=0.0,
        )
        for _ in range(500):
            det.record("attacker")
        for i in range(5):
            for _ in range(3):
                det.record(f"normal{i}")
        det._maybe_recompute(time.monotonic())
        assert det.is_anomalous("attacker") is True

    def test_normal_client_not_flagged(self) -> None:
        det = DDoSDetector(
            window=60.0, bucket_size=0.1, min_clients=3,
            min_rate_samples=1, z_threshold=3.0, recompute_interval=0.0,
        )
        for _ in range(30):
            det.record("attacker")
        for i in range(5):
            for _ in range(25):
                det.record(f"normal{i}")
        det._maybe_recompute(time.monotonic())
        assert det.is_anomalous("attacker") is False

    def test_global_rate(self) -> None:
        det = DDoSDetector(window=60.0, bucket_size=0.1)
        for _ in range(5):
            det.record("c1")
        rate = det.get_global_rate()
        assert rate > 0

    def test_stats(self) -> None:
        det = DDoSDetector(window=60.0, bucket_size=0.1)
        for _ in range(5):
            det.record("c1")
        stats = det.get_stats()
        assert stats["http_clients"] >= 1
        assert "http_distribution_mean" in stats
        assert "http_distribution_std" in stats


class TestProgressiveBanManager:
    """Test progressive auto-ban."""

    def test_no_ban_below_threshold(self) -> None:
        ban = ProgressiveBanManager(threshold=3)
        for _ in range(2):
            ban.record_violation("client1")
        assert ban.is_banned("client1") is False

    def test_ban_at_threshold(self) -> None:
        ban = ProgressiveBanManager(threshold=3)
        for _ in range(3):
            ban.record_violation("client1")
        assert ban.is_banned("client1") is True

    def test_ban_escalation(self) -> None:
        ban = ProgressiveBanManager(threshold=2, escalation=[0, 1, 5, 30])
        ban.record_violation("c1")
        ban.record_violation("c1")  # threshold met
        level1 = ban.get_ban_level("c1")

        ban.record_violation("c1")
        ban.record_violation("c1")  # more violations
        level2 = ban.get_ban_level("c1")

        assert level2 > level1

    def test_clear_ban(self) -> None:
        ban = ProgressiveBanManager(threshold=1)
        ban.record_violation("c1")
        assert ban.is_banned("c1") is True
        ban.clear_ban("c1")
        assert ban.is_banned("c1") is False

    def test_clear_all(self) -> None:
        ban = ProgressiveBanManager(threshold=1)
        ban.record_violation("c1")
        ban.record_violation("c2")
        count = ban.clear_all()
        assert count == 2
        assert ban.is_banned("c1") is False

    def test_get_active_bans(self) -> None:
        ban = ProgressiveBanManager(threshold=1)
        ban.record_violation("c1")
        active = ban.get_active_bans()
        assert "c1" in active

    def test_ban_expiry(self) -> None:
        ban = ProgressiveBanManager(threshold=1, escalation=[0, 0.01])
        ban.record_violation("c1")
        assert ban.is_banned("c1") is True
        time.sleep(0.02)
        assert ban.is_banned("c1") is False

    def test_retry_after(self) -> None:
        ban = ProgressiveBanManager(threshold=1, escalation=[0, 1.0])
        ban.record_violation("c1")
        retry = ban.get_retry_after("c1")
        assert retry is not None
        assert retry > 0


class TestCircuitBreaker:
    """Test circuit breaker."""

    def test_starts_closed(self) -> None:
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_trips_after_failures(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_success_resets(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(2):
            cb.record_failure()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_after_timeout(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request() is True

    def test_half_open_success_closes(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01, half_open_max_calls=1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.02)
        cb.allow_request()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.02)
        cb.allow_request()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_get_status(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        status = cb.get_status()
        assert status["failure_count"] == 1
        assert status["state"] == "closed"

    def test_manual_reset(self) -> None:
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED


class TestProtectionPipeline:
    """Test the unified protection pipeline."""

    def test_allows_normal_request(self) -> None:
        from drogue.protection.pipeline import ProtectionPipeline

        pipeline = ProtectionPipeline()
        import asyncio
        result = asyncio.run(
            pipeline.check("client1", {"client": {"host": "127.0.0.1"}})
        )
        assert result.allowed is True

    def test_blocks_banned_client(self) -> None:
        from drogue.protection.pipeline import ProtectionPipeline

        ban = ProgressiveBanManager(threshold=1, window=60.0)
        pipeline = ProtectionPipeline(ban=ban)
        ban.record_violation("bad_client")
        assert ban.is_banned("bad_client")

        import asyncio
        result = asyncio.run(
            pipeline.check("bad_client", {"client": {"host": "127.0.0.1"}})
        )
        assert result.allowed is False
        assert result.reason == "banned"
        assert result.status_code == 403

    def test_blocks_when_circuit_open(self) -> None:
        from drogue.protection.pipeline import ProtectionPipeline

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)
        pipeline = ProtectionPipeline(circuit=cb)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        import asyncio
        result = asyncio.run(
            pipeline.check("client1", {"client": {"host": "127.0.0.1"}})
        )
        assert result.allowed is False
        assert result.reason == "circuit_open"
        assert result.status_code == 503

    def test_records_violation(self) -> None:
        from drogue.protection.pipeline import ProtectionPipeline

        ban = ProgressiveBanManager(threshold=2, window=60.0)
        pipeline = ProtectionPipeline(ban=ban)
        pipeline.record_violation("client1")
        pipeline.record_violation("client1")
        assert ban.is_banned("client1")

    def test_records_success_for_circuit(self) -> None:
        from drogue.protection.pipeline import ProtectionPipeline

        cb = CircuitBreaker(failure_threshold=3)
        pipeline = ProtectionPipeline(circuit=cb)
        for _ in range(5):
            pipeline.record_success("client1")
        status = cb.get_status()
        assert status["failure_count"] == 0
        assert status["state"] == "closed"

    def test_get_stats(self) -> None:
        from drogue.protection.pipeline import ProtectionPipeline

        ddos = DDoSDetector(window=60.0, min_rate_samples=1)
        ban = ProgressiveBanManager(threshold=5, window=60.0)
        cb = CircuitBreaker(failure_threshold=3)
        pipeline = ProtectionPipeline(ddos=ddos, ban=ban, circuit=cb)
        stats = pipeline.get_stats()
        assert "ddos" in stats
        assert "ban" in stats
        assert "circuit" in stats
