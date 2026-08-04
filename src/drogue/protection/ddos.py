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
class DistributionStats:
    """Cross-sectional statistics of client rates using Welford's algorithm.

    Tracks mean and variance of client request rates across all active
    clients, enabling Z-score comparison of individual clients against
    the distribution of peer rates.
    """

    count: int = 0
    mean: float = 0.0
    m2: float = 0.0
    is_valid: bool = False

    @property
    def std(self) -> float:
        if self.count < 2 or not self.is_valid:
            return 0.0
        return math.sqrt(self.m2 / self.count)

    def update(self, rate: float) -> None:
        self.count += 1
        delta = rate - self.mean
        self.mean += delta / self.count
        delta2 = rate - self.mean
        self.m2 += delta * delta2

    def finalize(self) -> None:
        self.is_valid = self.count >= 2


@dataclass
class DDoSDetector:
    """Detects DDoS traffic using Z-score anomaly detection.

    Computes the distribution of request rates across all active clients
    and flags individual clients whose rate is statistically anomalous
    (high Z-score relative to the peer distribution).

    Supports both HTTP and WebSocket traffic with separate tracking.

    Algorithm:
        1. Maintain per-client request counts in time buckets
        2. Compute each client's sustained rate (req/s) over the window
        3. Compute mean and stddev across all client rates
        4. If a client's rate Z-score > threshold, flag as anomalous

    Usage:
        detector = DDoSDetector(window=60.0, z_threshold=3.0, min_clients=10)
        detector.record("192.168.1.1")
        detector.record_ws("192.168.1.1")
        is_attack = detector.is_anomalous("192.168.1.1")
    """

    window: float = 60.0
    z_threshold: float = 3.0
    min_clients: int = 10
    bucket_size: float = 1.0
    max_clients: int = 10000
    recompute_interval: float = 1.0
    min_rate_samples: int = 3
    rate_floor: float = 0.1

    # HTTP state
    _client_buckets: dict[str, deque[TrafficSample]] = field(default_factory=dict)
    _global_buckets: deque[TrafficSample] = field(default_factory=deque)
    _http_dist: DistributionStats = field(default_factory=DistributionStats)

    # WebSocket state
    _ws_client_buckets: dict[str, deque[TrafficSample]] = field(default_factory=dict)
    _ws_global_buckets: deque[TrafficSample] = field(default_factory=deque)
    _ws_dist: DistributionStats = field(default_factory=DistributionStats)

    # Timing
    _last_cleanup: float = field(default_factory=time.monotonic)
    _last_recompute: float = field(default_factory=time.monotonic)

    def record(self, client_key: str) -> None:
        """Record an HTTP request from a client."""
        now = time.monotonic()
        self._maybe_cleanup(now)
        self._maybe_recompute(now)

        client_bucket = int(now / self.bucket_size)

        # Record per-client
        if client_key not in self._client_buckets:
            self._client_buckets[client_key] = deque()
        buckets = self._client_buckets[client_key]
        if buckets and buckets[-1].timestamp == client_bucket:
            buckets[-1] = TrafficSample(
                timestamp=client_bucket, count=buckets[-1].count + 1
            )
        else:
            buckets.append(TrafficSample(timestamp=client_bucket, count=1))

        # Record global
        if self._global_buckets and self._global_buckets[-1].timestamp == client_bucket:
            self._global_buckets[-1] = TrafficSample(
                timestamp=client_bucket, count=self._global_buckets[-1].count + 1
            )
        else:
            self._global_buckets.append(
                TrafficSample(timestamp=client_bucket, count=1)
            )

    def record_ws(self, client_key: str) -> None:
        """Record a WebSocket connection/message from a client."""
        now = time.monotonic()
        self._maybe_cleanup(now)
        self._maybe_recompute(now)

        client_bucket = int(now / self.bucket_size)

        # Record per-client WebSocket
        if client_key not in self._ws_client_buckets:
            self._ws_client_buckets[client_key] = deque()
        ws_buckets = self._ws_client_buckets[client_key]
        if ws_buckets and ws_buckets[-1].timestamp == client_bucket:
            ws_buckets[-1] = TrafficSample(
                timestamp=client_bucket, count=ws_buckets[-1].count + 1
            )
        else:
            ws_buckets.append(TrafficSample(timestamp=client_bucket, count=1))

        # Record global WebSocket
        if self._ws_global_buckets and self._ws_global_buckets[-1].timestamp == client_bucket:
            self._ws_global_buckets[-1] = TrafficSample(
                timestamp=client_bucket, count=self._ws_global_buckets[-1].count + 1
            )
        else:
            self._ws_global_buckets.append(
                TrafficSample(timestamp=client_bucket, count=1)
            )

    def is_anomalous(self, client_key: str) -> bool:
        """Check if a client's request rate is anomalous (HTTP or combined)."""
        return self.is_http_anomalous(client_key) or self.is_ws_anomalous(client_key)

    def is_http_anomalous(self, client_key: str) -> bool:
        """Check if a client's HTTP request rate is anomalous.

        Compares the client's sustained rate against the distribution
        of rates across all active clients.
        """
        dist = self._http_dist
        if not dist.is_valid or dist.count < self.min_clients:
            return False

        now = time.monotonic()
        cutoff_bucket = int((now - self.window) / self.bucket_size)
        client_rate = self._compute_client_rate(client_key, cutoff_bucket)
        if client_rate is None:
            return False

        effective_std = max(dist.std, self.rate_floor)
        z_score = (client_rate - dist.mean) / effective_std
        return z_score > self.z_threshold

    def is_ws_anomalous(self, client_key: str) -> bool:
        """Check if a client's WebSocket rate is anomalous.

        Compares the client's sustained rate against the distribution
        of rates across all active WebSocket clients.
        """
        dist = self._ws_dist
        if not dist.is_valid or dist.count < self.min_clients:
            return False

        now = time.monotonic()
        cutoff_bucket = int((now - self.window) / self.bucket_size)
        client_rate = self._compute_ws_client_rate(client_key, cutoff_bucket)
        if client_rate is None:
            return False

        effective_std = max(dist.std, self.rate_floor)
        z_score = (client_rate - dist.mean) / effective_std
        return z_score > self.z_threshold

    def get_client_rate(self, client_key: str) -> float:
        """Get the current HTTP request rate (requests/second) for a client."""
        now = time.monotonic()
        cutoff_bucket = int((now - self.window) / self.bucket_size)
        rate = self._compute_client_rate(client_key, cutoff_bucket)
        return rate if rate is not None else 0.0

    def get_ws_client_rate(self, client_key: str) -> float:
        """Get the current WebSocket message rate (messages/second) for a client."""
        now = time.monotonic()
        cutoff_bucket = int((now - self.window) / self.bucket_size)
        rate = self._compute_ws_client_rate(client_key, cutoff_bucket)
        return rate if rate is not None else 0.0

    def get_global_rate(self) -> float:
        """Get the current global HTTP request rate."""
        now = time.monotonic()
        cutoff_bucket = int((now - self.window) / self.bucket_size)
        counts = [
            b.count for b in self._global_buckets if b.timestamp >= cutoff_bucket
        ]
        if not counts:
            return 0.0
        return sum(counts) / self.window

    def get_ws_global_rate(self) -> float:
        """Get the current global WebSocket message rate."""
        now = time.monotonic()
        cutoff_bucket = int((now - self.window) / self.bucket_size)
        counts = [
            b.count for b in self._ws_global_buckets if b.timestamp >= cutoff_bucket
        ]
        if not counts:
            return 0.0
        return sum(counts) / self.window

    def get_stats(self) -> dict[str, Any]:
        """Get current detector statistics."""
        http_dist = self._http_dist
        ws_dist = self._ws_dist
        return {
            "http_clients": len(self._client_buckets),
            "ws_clients": len(self._ws_client_buckets),
            "http_distribution_clients": http_dist.count,
            "http_distribution_mean": round(http_dist.mean, 4) if http_dist.is_valid else 0.0,
            "http_distribution_std": round(http_dist.std, 4) if http_dist.is_valid else 0.0,
            "ws_distribution_clients": ws_dist.count,
            "ws_distribution_mean": round(ws_dist.mean, 4) if ws_dist.is_valid else 0.0,
            "ws_distribution_std": round(ws_dist.std, 4) if ws_dist.is_valid else 0.0,
            "http_global_rate": round(self.get_global_rate(), 2),
            "ws_global_rate": round(self.get_ws_global_rate(), 2),
        }

    def _compute_client_rate(
        self, client_key: str, cutoff_bucket: int
    ) -> float | None:
        """Compute a single client's sustained rate (req/s) over the window."""
        buckets = self._client_buckets.get(client_key, deque())
        return self._compute_rate_from_buckets(buckets, cutoff_bucket)

    def _compute_ws_client_rate(
        self, client_key: str, cutoff_bucket: int
    ) -> float | None:
        """Compute a single client's sustained WebSocket rate (msg/s) over the window."""
        buckets = self._ws_client_buckets.get(client_key, deque())
        return self._compute_rate_from_buckets(buckets, cutoff_bucket)

    def _compute_rate_from_buckets(
        self, buckets: deque[TrafficSample], cutoff_bucket: int
    ) -> float | None:
        """Compute sustained rate from bucket data.

        Returns requests/second averaged over the full window duration,
        or None if insufficient data.
        """
        active_counts = [b.count for b in buckets if b.timestamp >= cutoff_bucket]
        if len(active_counts) < self.min_rate_samples:
            return None
        total = sum(active_counts)
        return total / self.window

    def _maybe_recompute(self, now: float) -> None:
        """Periodically recompute cross-sectional distribution stats."""
        if now - self._last_recompute < self.recompute_interval:
            return
        self._last_recompute = now
        self._recompute_http_distribution(now)
        self._recompute_ws_distribution(now)

    def _recompute_http_distribution(self, now: float) -> None:
        """Recompute the distribution of HTTP client rates."""
        cutoff_bucket = int((now - self.window) / self.bucket_size)
        dist = DistributionStats()

        for buckets in self._client_buckets.values():
            rate = self._compute_rate_from_buckets(buckets, cutoff_bucket)
            if rate is not None:
                dist.update(rate)

        dist.finalize()
        self._http_dist = dist

    def _recompute_ws_distribution(self, now: float) -> None:
        """Recompute the distribution of WebSocket client rates."""
        cutoff_bucket = int((now - self.window) / self.bucket_size)
        dist = DistributionStats()

        for buckets in self._ws_client_buckets.values():
            rate = self._compute_rate_from_buckets(buckets, cutoff_bucket)
            if rate is not None:
                dist.update(rate)

        dist.finalize()
        self._ws_dist = dist

    def _maybe_cleanup(self, now: float) -> None:
        """Clean up expired data every 10 seconds."""
        if now - self._last_cleanup < 10.0:
            return
        self._last_cleanup = now
        cutoff_bucket = int((now - self.window) / self.bucket_size)

        # Evict expired global buckets
        while self._global_buckets and self._global_buckets[0].timestamp < cutoff_bucket:
            self._global_buckets.popleft()
        while self._ws_global_buckets and self._ws_global_buckets[0].timestamp < cutoff_bucket:
            self._ws_global_buckets.popleft()

        # Evict expired per-client buckets, remove EMPTY clients only
        empty_http = []
        for key, buckets in self._client_buckets.items():
            while buckets and buckets[0].timestamp < cutoff_bucket:
                buckets.popleft()
            if not buckets:
                empty_http.append(key)
        for key in empty_http:
            del self._client_buckets[key]

        empty_ws = []
        for key, buckets in self._ws_client_buckets.items():
            while buckets and buckets[0].timestamp < cutoff_bucket:
                buckets.popleft()
            if not buckets:
                empty_ws.append(key)
        for key in empty_ws:
            del self._ws_client_buckets[key]

        # Hard cap eviction
        if len(self._client_buckets) > self.max_clients:
            excess = len(self._client_buckets) - self.max_clients
            sorted_keys = sorted(
                self._client_buckets.keys(),
                key=lambda k: len(self._client_buckets[k]),
            )
            for key in sorted_keys[:excess]:
                del self._client_buckets[key]

        if len(self._ws_client_buckets) > self.max_clients:
            excess = len(self._ws_client_buckets) - self.max_clients
            sorted_keys = sorted(
                self._ws_client_buckets.keys(),
                key=lambda k: len(self._ws_client_buckets[k]),
            )
            for key in sorted_keys[:excess]:
                del self._ws_client_buckets[key]
