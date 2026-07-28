"""Probe Pattern Detector for early attack detection.

Detects probe patterns that appear 30-120 seconds before the main
attack flood. Probes are low-rate reconnaissance requests that test
endpoint vulnerability before the full attack launches.

Probe signals:
- Many unique paths in short time
- High 404/error rate
- Rapid-fire requests to sensitive endpoints
- Scattered endpoint hits (vs normal user hitting same endpoints)

Impact: 30-120 seconds of early warning before attack flood.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("drogue.probes")


@dataclass
class ProbeEvent:
    """A single request event for probe detection."""

    timestamp: float
    path: str
    status_code: int
    method: str = "GET"


@dataclass
class ProbeSignal:
    """Detected probe signal for a client."""

    client_id: str
    unique_paths: int
    error_count: int
    total_count: int
    time_span: float
    threat_boost: float
    detected_at: float = field(default_factory=time.monotonic)


class ProbeDetector:
    """Detects probe patterns before main attack floods.

    Monitors request patterns per client and detects reconnaissance
    behavior that typically precedes DDoS attacks.

    Usage:
        detector = ProbeDetector(window=300.0, probe_threshold=3)

        # Record each request
        detector.record("192.168.1.1", "/api/login", 401)

        # Check if client is probing
        if detector.is_probing("192.168.1.1"):
            # Boost threat score
            boost = detector.get_threat_boost("192.168.1.1")
    """

    def __init__(
        self,
        window: float = 300.0,
        probe_threshold: int = 3,
        min_error_rate: float = 0.5,
        max_time_span: float = 60.0,
        threat_boost: float = 0.3,
        max_clients: int = 10000,
        cleanup_interval: float = 60.0,
    ):
        """Initialize the probe detector.

        Args:
            window: Time window to analyze (seconds).
            probe_threshold: Minimum requests to consider probe pattern.
            min_error_rate: Minimum error rate to flag as probe.
            max_time_span: Maximum time span for probe pattern (seconds).
            threat_boost: Threat score boost for detected probes.
            max_clients: Maximum clients to track.
            cleanup_interval: How often to clean up old data (seconds).
        """
        self.window = window
        self.probe_threshold = probe_threshold
        self.min_error_rate = min_error_rate
        self.max_time_span = max_time_span
        self.threat_boost = threat_boost
        self.max_clients = max_clients
        self.cleanup_interval = cleanup_interval

        self._client_events: dict[str, deque[ProbeEvent]] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        self._probing_clients: dict[str, ProbeSignal] = {}
        self._last_cleanup = time.monotonic()

        # Statistics
        self._stats = {
            "total_requests": 0,
            "probes_detected": 0,
            "clients_tracked": 0,
        }

    def record(
        self,
        client_id: str,
        path: str,
        status_code: int,
        method: str = "GET",
        timestamp: float | None = None,
    ) -> None:
        """Record a request event for probe detection.

        Args:
            client_id: Client identifier (IP, fingerprint, etc.).
            path: Request path.
            status_code: HTTP status code.
            method: HTTP method.
            timestamp: Optional timestamp (defaults to now).
        """
        now = timestamp or time.monotonic()
        event = ProbeEvent(
            timestamp=now,
            path=path,
            status_code=status_code,
            method=method,
        )

        self._client_events[client_id].append(event)
        self._stats["total_requests"] += 1

        # Cleanup old data periodically
        self._maybe_cleanup(now)

        # Check for probe pattern
        signal = self._detect_probe(client_id, now)
        if signal:
            self._probing_clients[client_id] = signal
            self._stats["probes_detected"] += 1
            logger.info(
                "probe_detected client=%s unique_paths=%d error_rate=%.2f threat_boost=%.2f",
                client_id,
                signal.unique_paths,
                signal.error_count / max(signal.total_count, 1),
                signal.threat_boost,
            )

    def is_probing(self, client_id: str) -> bool:
        """Check if a client is currently detected as probing.

        Args:
            client_id: Client identifier.

        Returns:
            True if client is detected as probing.
        """
        signal = self._probing_clients.get(client_id)
        if signal is None:
            return False

        # Check if signal is still within window
        if time.monotonic() - signal.detected_at > self.window:
            del self._probing_clients[client_id]
            return False

        return True

    def get_threat_boost(self, client_id: str) -> float:
        """Get threat score boost for a client.

        Args:
            client_id: Client identifier.

        Returns:
            Threat boost (0.0 if not probing, threat_boost if probing).
        """
        if self.is_probing(client_id):
            return self.threat_boost
        return 0.0

    def get_signal(self, client_id: str) -> ProbeSignal | None:
        """Get the probe signal for a client."""
        return self._probing_clients.get(client_id)

    def get_stats(self) -> dict[str, Any]:
        """Get detector statistics."""
        return {
            "total_requests": self._stats["total_requests"],
            "probes_detected": self._stats["probes_detected"],
            "active_probes": len(self._probing_clients),
            "clients_tracked": len(self._client_events),
        }

    def clear_client(self, client_id: str) -> bool:
        """Clear data for a specific client."""
        if client_id in self._client_events:
            del self._client_events[client_id]
        if client_id in self._probing_clients:
            del self._probing_clients[client_id]
            return True
        return False

    def clear_all(self) -> int:
        """Clear all data. Returns count of clients cleared."""
        count = len(self._client_events)
        self._client_events.clear()
        self._probing_clients.clear()
        return count

    def _detect_probe(self, client_id: str, now: float) -> ProbeSignal | None:
        """Detect probe pattern for a client."""
        events = self._client_events.get(client_id, deque())
        if len(events) < self.probe_threshold:
            return None

        # Get recent events within window
        cutoff = now - self.window
        recent = [e for e in events if e.timestamp >= cutoff]

        if len(recent) < self.probe_threshold:
            return None

        # Calculate probe signals
        unique_paths = len(set(e.path for e in recent))
        error_count = sum(1 for e in recent if e.status_code >= 400)
        time_span = recent[-1].timestamp - recent[0].timestamp

        # Check probe criteria
        error_rate = error_count / len(recent)

        if (
            unique_paths >= 3
            and error_rate >= self.min_error_rate
            and time_span <= self.max_time_span
        ):
            return ProbeSignal(
                client_id=client_id,
                unique_paths=unique_paths,
                error_count=error_count,
                total_count=len(recent),
                time_span=time_span,
                threat_boost=self.threat_boost,
            )

        return None

    def _maybe_cleanup(self, now: float) -> None:
        """Clean up old data periodically."""
        if now - self._last_cleanup < self.cleanup_interval:
            return

        self._last_cleanup = now
        cutoff = now - self.window

        # Clean old events
        empty_clients = []
        for client_id, events in self._client_events.items():
            while events and events[0].timestamp < cutoff:
                events.popleft()
            if not events:
                empty_clients.append(client_id)

        for client_id in empty_clients:
            del self._client_events[client_id]

        # Clean expired probe signals
        expired = [
            cid
            for cid, signal in self._probing_clients.items()
            if now - signal.detected_at > self.window
        ]
        for cid in expired:
            del self._probing_clients[cid]

        # Evict if over capacity
        if len(self._client_events) > self.max_clients:
            excess = len(self._client_events) - self.max_clients
            # Remove clients with fewest events
            sorted_clients = sorted(
                self._client_events.keys(),
                key=lambda k: len(self._client_events[k]),
            )
            for cid in sorted_clients[:excess]:
                del self._client_events[cid]
