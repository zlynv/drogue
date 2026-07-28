"""Adaptive rate limiting based on system metrics.

Dynamically adjusts rate limits based on CPU usage, memory pressure,
request latency, and time-of-day patterns.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("drogue.adaptive")

try:
    import psutil

    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


@dataclass
class LatencySample:
    """A latency measurement."""

    timestamp: float
    latency: float


@dataclass
class AdaptiveRateLimiter:
    """Dynamically adjusts rate limits based on system metrics.

    Monitors:
        - CPU usage
        - Memory usage
        - Request latency (p50, p95, p99)
        - Time-of-day patterns (optional)

    When system is under pressure, limits are reduced proportionally.

    Usage:
        adaptive = AdaptiveRateLimiter(
            cpu_threshold=0.8,
            memory_threshold=0.8,
            latency_threshold=1.0,
        )

        # Get effective limit based on current system state
        effective_limit = adaptive.get_effective_limit(base_limit=100)
    """

    cpu_threshold: float = 0.8
    memory_threshold: float = 0.8
    latency_threshold: float = 1.0
    check_interval: float = 5.0
    latency_window: float = 60.0
    max_latency_samples: int = 1000

    # Internal state
    _latency_samples: deque[LatencySample] = field(default_factory=deque)
    _last_check: float = field(default_factory=time.monotonic)
    _cached_cpu: float = field(default=0.0, init=False, repr=False)
    _cached_memory: float = field(default=0.0, init=False, repr=False)
    _cpu_reduction: float = field(default=1.0, init=False, repr=False)
    _memory_reduction: float = field(default=1.0, init=False, repr=False)
    _latency_reduction: float = field(default=1.0, init=False, repr=False)

    def __post_init__(self) -> None:
        """Check if psutil is available."""
        if not _HAS_PSUTIL:
            logger.warning(
                "psutil not installed. Adaptive rate limiting will use "
                "latency-based adjustments only. Install with: pip install psutil"
            )

    def record_latency(self, latency: float) -> None:
        """Record a request latency measurement (in seconds)."""
        now = time.monotonic()
        self._latency_samples.append(LatencySample(timestamp=now, latency=latency))

        # Trim old samples
        cutoff = now - self.latency_window
        while self._latency_samples and self._latency_samples[0].timestamp < cutoff:
            self._latency_samples.popleft()

        # Hard cap
        while len(self._latency_samples) > self.max_latency_samples:
            self._latency_samples.popleft()

    def get_effective_limit(self, base_limit: int) -> int:
        """Get the effective rate limit based on current system metrics.

        Args:
            base_limit: The configured rate limit.

        Returns:
            The adjusted limit (always >= 1).
        """
        now = time.monotonic()

        # Periodic check
        if now - self._last_check >= self.check_interval:
            self._update_metrics()
            self._last_check = now

        # Compute combined reduction factor
        reduction = min(self._cpu_reduction, self._memory_reduction, self._latency_reduction)

        # Apply reduction (never go below 1)
        effective = max(1, int(base_limit * reduction))

        return effective

    def get_metrics(self) -> dict[str, Any]:
        """Get current adaptive metrics."""
        now = time.monotonic()
        if now - self._last_check >= self.check_interval:
            self._update_metrics()
            self._last_check = now

        return {
            "cpu_usage": self._cached_cpu,
            "memory_usage": self._cached_memory,
            "cpu_threshold": self.cpu_threshold,
            "memory_threshold": self.memory_threshold,
            "cpu_reduction": self._cpu_reduction,
            "memory_reduction": self._memory_reduction,
            "latency_reduction": self._latency_reduction,
            "latency_p50": self._get_percentile(0.5),
            "latency_p95": self._get_percentile(0.95),
            "latency_p99": self._get_percentile(0.99),
            "latency_samples": len(self._latency_samples),
        }

    def _update_metrics(self) -> None:
        """Update system metrics and compute reduction factors."""
        if _HAS_PSUTIL:
            try:
                self._cached_cpu = psutil.cpu_count() and psutil.cpu_percent(interval=0) / 100.0
                mem = psutil.virtual_memory()
                self._cached_memory = mem.percent / 100.0
            except Exception:
                self._cached_cpu = 0.0
                self._cached_memory = 0.0

        # CPU reduction: linear from 1.0 at threshold to 0.1 at 100%
        if self._cached_cpu > self.cpu_threshold:
            excess = (self._cached_cpu - self.cpu_threshold) / (1.0 - self.cpu_threshold)
            self._cpu_reduction = max(0.1, 1.0 - (excess * 0.9))
        else:
            self._cpu_reduction = 1.0

        # Memory reduction: linear from 1.0 at threshold to 0.1 at 100%
        if self._cached_memory > self.memory_threshold:
            excess = (self._cached_memory - self.memory_threshold) / (1.0 - self.memory_threshold)
            self._memory_reduction = max(0.1, 1.0 - (excess * 0.9))
        else:
            self._memory_reduction = 1.0

        # Latency reduction: based on p95 latency
        p95 = self._get_percentile(0.95)
        if p95 > self.latency_threshold:
            # Reduce proportionally to how much p95 exceeds threshold
            ratio = p95 / self.latency_threshold
            self._latency_reduction = max(0.1, 1.0 / ratio)
        else:
            self._latency_reduction = 1.0

    def _get_percentile(self, percentile: float) -> float:
        """Get a latency percentile."""
        if not self._latency_samples:
            return 0.0

        latencies = sorted(s.latency for s in self._latency_samples)
        idx = int(len(latencies) * percentile)
        idx = min(idx, len(latencies) - 1)
        return latencies[idx]
