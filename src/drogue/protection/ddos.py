"""DDoS traffic analysis using Z-score anomaly detection.

Monitors request rates per client and detects statistical outliers
that indicate DDoS attacks or scanning activity.
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrafficSample:
    """A single traffic measurement."""

    timestamp: float
    count: int


@dataclass
class DDoSDetector:
    """Detects DDoS traffic using Z-score anomaly detection.

    Tracks request rates per client over a sliding window and flags
    clients whose request rate is statistically anomalous.

    Supports both HTTP and WebSocket traffic with separate tracking.

    Algorithm:
        1. Maintain a rolling window of request counts per time bucket
        2. Compute mean and stddev of request rates across all clients
        3. If a client's rate Z-score > threshold, flag as anomalous

    Usage:
        detector = DDoSDetector(window=60.0, z_threshold=3.0, min_samples=100)
        detector.record("192.168.1.1")
        detector.record_ws("192.168.1.1")  # WebSocket connection
        is_attack = detector.is_anomalous("192.168.1.1")
    """

    window: float = 60.0
    z_threshold: float = 3.0
    min_samples: int = 100
    bucket_size: float = 1.0
    max_clients: int = 10000

    # Internal state
    _client_counts: dict[str, deque[TrafficSample]] = field(default_factory=dict)
    _global_counts: deque[TrafficSample] = field(default_factory=deque)
    _last_cleanup: float = field(default_factory=time.monotonic)

    # WebSocket-specific tracking
    _ws_client_counts: dict[str, deque[TrafficSample]] = field(default_factory=dict)
    _ws_global_counts: deque[TrafficSample] = field(default_factory=deque)

    def record(self, client_key: str) -> None:
        """Record a request from a client."""
        now = time.monotonic()
        self._maybe_cleanup(now)

        # Record per-client
        if client_key not in self._client_counts:
            self._client_counts[client_key] = deque()
        client_bucket = int(now / self.bucket_size)
        buckets = self._client_counts[client_key]
        if buckets and buckets[-1].timestamp == client_bucket:
            buckets[-1] = TrafficSample(timestamp=client_bucket, count=buckets[-1].count + 1)
        else:
            buckets.append(TrafficSample(timestamp=client_bucket, count=1))

        # Record global
        if self._global_counts and self._global_counts[-1].timestamp == client_bucket:
            self._global_counts[-1] = TrafficSample(
                timestamp=client_bucket, count=self._global_counts[-1].count + 1
            )
        else:
            self._global_counts.append(TrafficSample(timestamp=client_bucket, count=1))

    def record_ws(self, client_key: str) -> None:
        """Record a WebSocket connection/message from a client."""
        now = time.monotonic()
        self._maybe_cleanup(now)

        client_bucket = int(now / self.bucket_size)

        # Record per-client WebSocket
        if client_key not in self._ws_client_counts:
            self._ws_client_counts[client_key] = deque()
        ws_buckets = self._ws_client_counts[client_key]
        if ws_buckets and ws_buckets[-1].timestamp == client_bucket:
            ws_buckets[-1] = TrafficSample(
                timestamp=client_bucket, count=ws_buckets[-1].count + 1
            )
        else:
            ws_buckets.append(TrafficSample(timestamp=client_bucket, count=1))

        # Record global WebSocket
        if self._ws_global_counts and self._ws_global_counts[-1].timestamp == client_bucket:
            self._ws_global_counts[-1] = TrafficSample(
                timestamp=client_bucket, count=self._ws_global_counts[-1].count + 1
            )
        else:
            self._ws_global_counts.append(TrafficSample(timestamp=client_bucket, count=1))

    def is_anomalous(self, client_key: str) -> bool:
        """Check if a client's request rate is anomalous (HTTP or combined)."""
        return self.is_http_anomalous(client_key) or self.is_ws_anomalous(client_key)

    def is_http_anomalous(self, client_key: str) -> bool:
        """Check if a client's HTTP request rate is anomalous."""
        now = time.monotonic()
        cutoff = now - self.window

        # Get client rates
        client_rates = self._get_rates(client_key, cutoff)
        if not client_rates:
            return False

        # Get global rates
        global_rates = self._get_global_rates(cutoff)
        if len(global_rates) < self.min_samples:
            return False

        # Client's average rate
        client_avg = sum(client_rates) / len(client_rates)

        # Global statistics
        global_mean = sum(global_rates) / len(global_rates)
        global_var = sum((r - global_mean) ** 2 for r in global_rates) / len(global_rates)
        global_std = math.sqrt(global_var) if global_var > 0 else 1.0

        # Z-score
        z_score = (client_avg - global_mean) / global_std

        return z_score > self.z_threshold

    def is_ws_anomalous(self, client_key: str) -> bool:
        """Check if a client's WebSocket rate is anomalous."""
        now = time.monotonic()
        cutoff = now - self.window

        # Get client WebSocket rates
        client_rates = self._get_ws_rates(client_key, cutoff)
        if not client_rates:
            return False

        # Get global WebSocket rates
        global_rates = self._get_ws_global_rates(cutoff)
        if len(global_rates) < self.min_samples:
            return False

        # Client's average rate
        client_avg = sum(client_rates) / len(client_rates)

        # Global statistics
        global_mean = sum(global_rates) / len(global_rates)
        global_var = sum((r - global_mean) ** 2 for r in global_rates) / len(global_rates)
        global_std = math.sqrt(global_var) if global_var > 0 else 1.0

        # Z-score
        z_score = (client_avg - global_mean) / global_std

        return z_score > self.z_threshold

    def get_client_rate(self, client_key: str) -> float:
        """Get the current HTTP request rate (requests/second) for a client."""
        now = time.monotonic()
        cutoff = now - self.window
        rates = self._get_rates(client_key, cutoff)
        if not rates:
            return 0.0
        return sum(rates) / len(rates) / self.bucket_size

    def get_ws_client_rate(self, client_key: str) -> float:
        """Get the current WebSocket message rate (messages/second) for a client."""
        now = time.monotonic()
        cutoff = now - self.window
        rates = self._get_ws_rates(client_key, cutoff)
        if not rates:
            return 0.0
        return sum(rates) / len(rates) / self.bucket_size

    def get_global_rate(self) -> float:
        """Get the current global HTTP request rate."""
        now = time.monotonic()
        cutoff = now - self.window
        rates = self._get_global_rates(cutoff)
        if not rates:
            return 0.0
        return sum(rates) / len(rates) / self.bucket_size

    def get_ws_global_rate(self) -> float:
        """Get the current global WebSocket message rate."""
        now = time.monotonic()
        cutoff = now - self.window
        rates = self._get_ws_global_rates(cutoff)
        if not rates:
            return 0.0
        return sum(rates) / len(rates) / self.bucket_size

    def get_stats(self) -> dict[str, Any]:
        """Get current detector statistics."""
        now = time.monotonic()
        cutoff = now - self.window
        global_rates = self._get_global_rates(cutoff)
        ws_global_rates = self._get_ws_global_rates(cutoff)

        stats: dict[str, Any] = {
            "http_clients": len(self._client_counts),
            "ws_clients": len(self._ws_client_counts),
        }

        if global_rates:
            mean = sum(global_rates) / len(global_rates)
            var = sum((r - mean) ** 2 for r in global_rates) / len(global_rates)
            stats["http_global_rate"] = mean / self.bucket_size
            stats["http_mean"] = mean
            stats["http_std"] = math.sqrt(var) if var > 0 else 0.0
        else:
            stats["http_global_rate"] = 0
            stats["http_mean"] = 0
            stats["http_std"] = 0

        if ws_global_rates:
            ws_mean = sum(ws_global_rates) / len(ws_global_rates)
            ws_var = sum((r - ws_mean) ** 2 for r in ws_global_rates) / len(ws_global_rates)
            stats["ws_global_rate"] = ws_mean / self.bucket_size
            stats["ws_mean"] = ws_mean
            stats["ws_std"] = math.sqrt(ws_var) if ws_var > 0 else 0.0
        else:
            stats["ws_global_rate"] = 0
            stats["ws_mean"] = 0
            stats["ws_std"] = 0

        return stats

    def _get_rates(self, client_key: str, cutoff: float) -> list[int]:
        """Get HTTP request counts for a client within the window."""
        buckets = self._client_counts.get(client_key, deque())
        return [b.count for b in buckets if b.timestamp * self.bucket_size >= cutoff]

    def _get_ws_rates(self, client_key: str, cutoff: float) -> list[int]:
        """Get WebSocket message counts for a client within the window."""
        buckets = self._ws_client_counts.get(client_key, deque())
        return [b.count for b in buckets if b.timestamp * self.bucket_size >= cutoff]

    def _get_global_rates(self, cutoff: float) -> list[int]:
        """Get global HTTP request counts within the window."""
        return [b.count for b in self._global_counts if b.timestamp * self.bucket_size >= cutoff]

    def _get_ws_global_rates(self, cutoff: float) -> list[int]:
        """Get global WebSocket message counts within the window."""
        return [
            b.count for b in self._ws_global_counts if b.timestamp * self.bucket_size >= cutoff
        ]

    def _maybe_cleanup(self, now: float) -> None:
        """Clean up expired data every 10 seconds."""
        if now - self._last_cleanup < 10.0:
            return
        self._last_cleanup = now
        cutoff_bucket = int((now - self.window) / self.bucket_size)

        # Clean global HTTP
        while self._global_counts and self._global_counts[0].timestamp < cutoff_bucket:
            self._global_counts.popleft()

        # Clean global WebSocket
        while self._ws_global_counts and self._ws_global_counts[0].timestamp < cutoff_bucket:
            self._ws_global_counts.popleft()

        # Clean per-client HTTP: remove empty or low-sample clients
        empty_clients = []
        for key, buckets in self._client_counts.items():
            while buckets and buckets[0].timestamp < cutoff_bucket:
                buckets.popleft()
            if not buckets or len(buckets) < self.min_samples:
                empty_clients.append(key)
        for key in empty_clients:
            del self._client_counts[key]

        # Clean per-client WebSocket: remove empty or low-sample clients
        empty_ws_clients = []
        for key, buckets in self._ws_client_counts.items():
            while buckets and buckets[0].timestamp < cutoff_bucket:
                buckets.popleft()
            if not buckets or len(buckets) < self.min_samples:
                empty_ws_clients.append(key)
        for key in empty_ws_clients:
            del self._ws_client_counts[key]

        # Hard cap: if still over limit, evict oldest clients
        if len(self._client_counts) > self.max_clients:
            excess = len(self._client_counts) - self.max_clients
            sorted_clients = sorted(
                self._client_counts.keys(),
                key=lambda k: len(self._client_counts[k]),
            )
            for key in sorted_clients[:excess]:
                del self._client_counts[key]

        if len(self._ws_client_counts) > self.max_clients:
            excess = len(self._ws_client_counts) - self.max_clients
            sorted_clients = sorted(
                self._ws_client_counts.keys(),
                key=lambda k: len(self._ws_client_counts[k]),
            )
            for key in sorted_clients[:excess]:
                del self._ws_client_counts[key]
