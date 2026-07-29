"""Metrics collection for rate limiting.

Provides a framework-agnostic metrics collector that can export
to Prometheus, StatsD, or custom backends.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Counter:
    """Thread-safe counter."""

    value: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def inc(self, amount: int = 1) -> None:
        with self._lock:
            self.value += amount

    def get(self) -> int:
        with self._lock:
            return self.value


@dataclass
class Gauge:
    """Thread-safe gauge."""

    value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set(self, val: float) -> None:
        with self._lock:
            self.value = val

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self.value += amount

    def dec(self, amount: float = 1.0) -> None:
        with self._lock:
            self.value -= amount

    def get(self) -> float:
        with self._lock:
            return self.value


@dataclass
class Histogram:
    """Simple histogram for latency tracking."""

    buckets: list[float] = field(
        default_factory=lambda: [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
    )
    _counts: dict[float, int] = field(default_factory=dict)
    _total: float = 0.0
    _count: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def observe(self, value: float) -> None:
        with self._lock:
            self._total += value
            self._count += 1
            for bucket in self.buckets:
                if value <= bucket:
                    self._counts[bucket] = self._counts.get(bucket, 0) + 1

    def get_count(self) -> int:
        with self._lock:
            return self._count

    def get_sum(self) -> float:
        with self._lock:
            return self._total

    def get_average(self) -> float:
        with self._lock:
            return self._total / self._count if self._count > 0 else 0.0


@dataclass
class DrogueMetrics:
    """Metrics collector for drogue rate limiting.

    Collects:
        - Request counts (allowed vs rejected)
        - Ban counts and levels
        - Circuit breaker state changes
        - DDoS detection events
        - Algorithm latency

    Usage:
        metrics = DrogueMetrics()
        metrics.record_allowed("GET:/api/data")
        metrics.record_rejected("GET:/api/data")
        metrics.record_ban("192.168.1.1", level=2)

        # Export as Prometheus text
        print(metrics.to_prometheus())
    """

    max_routes: int = 500

    # Request metrics
    requests_allowed: Counter = field(default_factory=Counter)
    requests_rejected: Counter = field(default_factory=Counter)

    # Per-route metrics
    _route_allowed: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    _route_rejected: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))

    # Ban metrics
    bans_total: Counter = field(default_factory=Counter)
    bans_active: Gauge = field(default_factory=Gauge)

    # DDoS metrics
    ddos_detections: Counter = field(default_factory=Counter)

    # Circuit breaker metrics
    circuit_trips: Counter = field(default_factory=Counter)
    circuit_state: Gauge = field(default_factory=Gauge)

    # Latency
    check_latency: Histogram = field(default_factory=Histogram)

    def _evict_if_needed(self) -> None:
        """Evict oldest routes if over max_routes cap."""
        total = len(self._route_allowed) + len(self._route_rejected)
        if total <= self.max_routes:
            return
        # Collect all route keys and their total counts
        all_routes: dict[str, int] = {}
        for route, counter in self._route_allowed.items():
            all_routes[route] = all_routes.get(route, 0) + counter.get()
        for route, counter in self._route_rejected.items():
            all_routes[route] = all_routes.get(route, 0) + counter.get()
        # Evict lowest-traffic routes
        excess = total - self.max_routes
        sorted_routes = sorted(all_routes.keys(), key=lambda r: all_routes[r])
        for route in sorted_routes[:excess]:
            self._route_allowed.pop(route, None)
            self._route_rejected.pop(route, None)

    def record_allowed(self, route: str = "unknown") -> None:
        """Record an allowed request."""
        self.requests_allowed.inc()
        self._route_allowed[route].inc()
        self._evict_if_needed()

    def record_rejected(self, route: str = "unknown") -> None:
        """Record a rejected request."""
        self.requests_rejected.inc()
        self._route_rejected[route].inc()
        self._evict_if_needed()

    def record_ban(self, key: str, level: int = 1) -> None:
        """Record a ban event."""
        self.bans_total.inc()
        self.bans_active.inc()

    def record_ban_expired(self) -> None:
        """Record a ban expiry."""
        self.bans_active.dec()

    def record_ddos_detection(self, key: str) -> None:
        """Record a DDoS detection event."""
        self.ddos_detections.inc()

    def record_circuit_trip(self) -> None:
        """Record a circuit breaker trip."""
        self.circuit_trips.inc()
        self.circuit_state.set(1.0)

    def record_circuit_reset(self) -> None:
        """Record a circuit breaker reset."""
        self.circuit_state.set(0.0)

    def record_check_latency(self, seconds: float) -> None:
        """Record rate limit check latency."""
        self.check_latency.observe(seconds)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "requests_allowed": self.requests_allowed.get(),
            "requests_rejected": self.requests_rejected.get(),
            "bans_total": self.bans_total.get(),
            "bans_active": self.bans_active.get(),
            "ddos_detections": self.ddos_detections.get(),
            "circuit_trips": self.circuit_trips.get(),
            "circuit_state": self.circuit_state.get(),
            "check_latency_avg": self.check_latency.get_average(),
            "check_latency_count": self.check_latency.get_count(),
        }

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []

        lines.append("# HELP drogue_requests_total Total rate limit checks")
        lines.append("# TYPE drogue_requests_total counter")
        lines.append(f"drogue_requests_total{{status=\"allowed\"}} {self.requests_allowed.get()}")
        lines.append(f"drogue_requests_total{{status=\"rejected\"}} {self.requests_rejected.get()}")

        lines.append("# HELP drogue_bans_total Total bans issued")
        lines.append("# TYPE drogue_bans_total counter")
        lines.append(f"drogue_bans_total {self.bans_total.get()}")

        lines.append("# HELP drogue_bans_active Currently active bans")
        lines.append("# TYPE drogue_bans_active gauge")
        lines.append(f"drogue_bans_active {self.bans_active.get()}")

        lines.append("# HELP drogue_ddos_detections_total DDoS detections")
        lines.append("# TYPE drogue_ddos_detections_total counter")
        lines.append(f"drogue_ddos_detections_total {self.ddos_detections.get()}")

        lines.append("# HELP drogue_circuit_trips_total Circuit breaker trips")
        lines.append("# TYPE drogue_circuit_trips_total counter")
        lines.append(f"drogue_circuit_trips_total {self.circuit_trips.get()}")

        lines.append("# HELP drogue_check_latency_seconds Rate limit check latency")
        lines.append("# TYPE drogue_check_latency_seconds summary")
        lines.append(
            f"drogue_check_latency_seconds_count {self.check_latency.get_count()}"
        )
        lines.append(
            f"drogue_check_latency_seconds_sum {self.check_latency.get_sum():.6f}"
        )

        # Per-route metrics
        lines.append("# HELP drogue_route_requests_total Per-route request counts")
        lines.append("# TYPE drogue_route_requests_total counter")
        for route, counter in sorted(self._route_allowed.items()):
            lines.append(
                f'drogue_route_requests_total{{route="{route}",status="allowed"}} {counter.get()}'
            )
        for route, counter in sorted(self._route_rejected.items()):
            lines.append(
                f'drogue_route_requests_total{{route="{route}",status="rejected"}} {counter.get()}'
            )

        return "\n".join(lines) + "\n"
