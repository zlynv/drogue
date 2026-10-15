# Observability API

## DrogueMetrics

```python
from drogue.observability.metrics import DrogueMetrics

metrics = DrogueMetrics(max_routes=500)

# Record events
metrics.record_allowed(route="/api/data")
metrics.record_rejected(route="/api/data")
metrics.record_check_latency(0.000043)
metrics.record_ban("192.168.1.1", level=1)
metrics.record_ban_expired()
metrics.record_ddos_detection("192.168.1.1")
metrics.record_circuit_trip()
metrics.record_circuit_reset()

# Export
prometheus_output = metrics.to_prometheus()  # Prometheus text format
summary = metrics.get_summary()              # dict with all counts
```

`get_summary()` returns `requests_allowed`, `requests_rejected`,
`bans_total`, `bans_active`, `ddos_detections`, `circuit_trips`,
`circuit_state`, `check_latency_avg`, `check_latency_count`.
`to_prometheus()` emits `drogue_requests_total{status="allowed"|"rejected"}`,
`drogue_bans_total`, `drogue_bans_active`, `drogue_ddos_detections_total`,
`drogue_circuit_trips_total`, `drogue_check_latency_seconds_count/_sum`
and per-route `drogue_route_requests_total{route,status}`. See
[Metrics](../observability/metrics.md) for the full exposition.

## StructuredRateLimitLogger

```python
import logging
from drogue.observability.logging import StructuredRateLimitLogger

logger = StructuredRateLimitLogger(logger_name="drogue", level=logging.INFO)
logger.log_allowed(key="192.168.1.1", route="/api/data", remaining=9, limit=10)
logger.log_rejected(key="192.168.1.1", route="/api/data", retry_after=30, limit=10)
```

Event names are `rate_limit_allowed`, `rate_limit_rejected`,
`ban_issued`, `ban_expired`, `ddos_detected`, `circuit_breaker` and
`error`. See [Logging](../observability/logging.md) for the field tables.

## DrogueTelemetry

```python
from drogue.observability.opentelemetry import DrogueTelemetry

telemetry = DrogueTelemetry(service_name="my-api")

# Traces
with telemetry.trace_rate_limit_check(key="192.168.1.1", limit=10) as span:
    ...

# Metrics
telemetry.record_rate_limit_result(allowed=True, route="/api/data")
telemetry.record_latency(0.000043, route="/api/data")
```

Instruments are `drogue.rate_limit.requests`, `drogue.rate_limit.blocked`,
`drogue.rate_limit.latency`, `drogue.ddos.detected`, `drogue.ban.issued`
and `drogue.circuit_breaker.state_change`. See
[OpenTelemetry](../observability/opentelemetry.md) for attributes.
