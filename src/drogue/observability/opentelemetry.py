"""OpenTelemetry integration for drogue.

Provides tracing and metrics export for rate limiting events,
DDoS detection, circuit breaker state changes, and ban events.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("drogue.opentelemetry")

try:
    from opentelemetry import metrics, trace

    _HAS_OTEL = True
except ImportError:
    _HAS_OTEL = False


@dataclass
class DrogueTelemetry:
    """OpenTelemetry integration for drogue.

    Provides:
        - Rate limit check spans
        - Rate limit metrics (counters, histograms)
        - DDoS detection events
        - Circuit breaker state changes
        - Ban events

    Usage:
        telemetry = DrogueTelemetry(service_name="my-api")

        # Instrument rate limit checks
        with telemetry.trace_rate_limit_check(key="192.168.1.1", limit=100):
            result = await limiter._check(key, rule)

        # Record metrics
        telemetry.record_rate_limit_result(allowed=True, route="/api/data")
    """

    service_name: str = "drogue"
    enabled: bool = True

    # Internal state
    _tracer: Any = field(default=None, init=False, repr=False)
    _meter: Any = field(default=None, init=False, repr=False)
    _request_counter: Any = field(default=None, init=False, repr=False)
    _blocked_counter: Any = field(default=None, init=False, repr=False)
    _latency_histogram: Any = field(default=None, init=False, repr=False)
    _ddos_counter: Any = field(default=None, init=False, repr=False)
    _ban_counter: Any = field(default=None, init=False, repr=False)
    _circuit_counter: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize OpenTelemetry instruments."""
        if not _HAS_OTEL:
            logger.warning(
                "OpenTelemetry not installed. Telemetry disabled. "
                "Install with: pip install opentelemetry-api opentelemetry-sdk"
            )
            self.enabled = False
            return

        if not self.enabled:
            return

        try:
            self._tracer = trace.get_tracer(self.service_name)
            self._meter = metrics.get_meter(self.service_name)

            # Create instruments
            self._request_counter = self._meter.create_counter(
                name="drogue.rate_limit.requests",
                description="Total rate limit requests",
                unit="1",
            )
            self._blocked_counter = self._meter.create_counter(
                name="drogue.rate_limit.blocked",
                description="Total blocked requests",
                unit="1",
            )
            self._latency_histogram = self._meter.create_histogram(
                name="drogue.rate_limit.latency",
                description="Rate limit check latency",
                unit="s",
            )
            self._ddos_counter = self._meter.create_counter(
                name="drogue.ddos.detected",
                description="DDoS attacks detected",
                unit="1",
            )
            self._ban_counter = self._meter.create_counter(
                name="drogue.ban.issued",
                description="Bans issued",
                unit="1",
            )
            self._circuit_counter = self._meter.create_counter(
                name="drogue.circuit_breaker.state_change",
                description="Circuit breaker state changes",
                unit="1",
            )
        except Exception as e:
            logger.warning("Failed to initialize OpenTelemetry: %s", e)
            self.enabled = False

    def trace_rate_limit_check(self, key: str, limit: int, route: str = "") -> Any:
        """Context manager for tracing a rate limit check.

        Usage:
            with telemetry.trace_rate_limit_check(key="192.168.1.1", limit=100):
                result = await limiter._check(key, rule)
        """
        if not self.enabled or not self._tracer:
            return _DummyContext()

        attributes = {
            "drogue.rate_limit.key": key,
            "drogue.rate_limit.limit": limit,
        }
        if route:
            attributes["drogue.rate_limit.route"] = route

        return self._tracer.start_as_current_span(
            name="drogue.rate_limit_check",
            attributes=attributes,
        )

    def record_rate_limit_result(
        self,
        allowed: bool,
        route: str = "",
        key: str = "",
        remaining: int = 0,
        retry_after: float = 0,
    ) -> None:
        """Record a rate limit check result."""
        if not self.enabled:
            return

        attributes = {
            "drogue.rate_limit.allowed": allowed,
            "drogue.rate_limit.route": route,
        }

        if self._request_counter:
            self._request_counter.add(1, attributes)

        if not allowed and self._blocked_counter:
            self._blocked_counter.add(1, attributes)

    def record_latency(self, latency: float, route: str = "") -> None:
        """Record rate limit check latency."""
        if not self.enabled or not self._latency_histogram:
            return

        attributes = {"drogue.rate_limit.route": route}
        self._latency_histogram.record(latency, attributes)

    def record_ddos_detected(self, client_key: str, z_score: float) -> None:
        """Record a DDoS detection event."""
        if not self.enabled or not self._ddos_counter:
            return

        attributes = {
            "drogue.ddos.client": client_key,
            "drogue.ddos.z_score": z_score,
        }
        self._ddos_counter.add(1, attributes)

    def record_ban_issued(self, key: str, level: int, duration: float) -> None:
        """Record a ban event."""
        if not self.enabled or not self._ban_counter:
            return

        attributes = {
            "drogue.ban.key": key,
            "drogue.ban.level": level,
            "drogue.ban.duration": duration,
        }
        self._ban_counter.add(1, attributes)

    def record_circuit_breaker_change(self, state: str, key: str = "") -> None:
        """Record a circuit breaker state change."""
        if not self.enabled or not self._circuit_counter:
            return

        attributes = {
            "drogue.circuit_breaker.state": state,
            "drogue.circuit_breaker.key": key,
        }
        self._circuit_counter.add(1, attributes)


class _DummyContext:
    """Dummy context manager when telemetry is disabled."""

    def __enter__(self) -> _DummyContext:
        return self

    def __exit__(self, *args: Any) -> None:
        pass
