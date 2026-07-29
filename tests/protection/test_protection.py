"""Tests for protection layer — DDoS, ban, circuit breaker."""
from __future__ import annotations

import time

from drogue.protection.ban import ProgressiveBanManager
from drogue.protection.circuit import CircuitBreaker, CircuitState
from drogue.protection.ddos import DDoSDetector


class TestDDoSDetector:
    """Test Z-score anomaly detection."""

    def test_record_and_rate(self) -> None:
        det = DDoSDetector(window=60.0, bucket_size=0.1)
        for _ in range(10):
            det.record("client1")
        rate = det.get_client_rate("client1")
        assert rate > 0

    def test_not_anomalous_with_few_samples(self) -> None:
        det = DDoSDetector(min_samples=100)
        det.record("attacker")
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
