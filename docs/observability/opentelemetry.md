# OpenTelemetry

## Setup

```bash
pip install drogue[opentelemetry]
```

```python
from drogue.observability.opentelemetry import DrogueTelemetry

telemetry = DrogueTelemetry(service_name="my-api")
```

Without `drogue[opentelemetry]` installed the object disables itself
(`enabled=False`) and every method becomes a no-op.

## Traces

```python
with telemetry.trace_rate_limit_check(key="192.168.1.1", limit=10, route="/api/data") as span:
    ...
```

The span is named `drogue.rate_limit_check` and carries
`drogue.rate_limit.key`, `drogue.rate_limit.limit` and (when given)
`drogue.rate_limit.route`.

## Metrics

```python
telemetry.record_rate_limit_result(allowed=True, route="/api/data")
telemetry.record_latency(0.000043, route="/api/data")
telemetry.record_ddos_detected("192.168.1.1", z_score=4.2)
telemetry.record_ban_issued("192.168.1.1", level=2, duration=600.0)
telemetry.record_circuit_breaker_change("open")
```

Instruments (all prefixed for the configured meter):

| OTel name | Type | Records |
|-----------|------|---------|
| `drogue.rate_limit.requests` | Counter | every decision, attrs `drogue.rate_limit.allowed`, `drogue.rate_limit.route` |
| `drogue.rate_limit.blocked` | Counter | denied decisions only |
| `drogue.rate_limit.latency` | Histogram (s) | check latency per route |
| `drogue.ddos.detected` | Counter | attrs `drogue.ddos.client`, `drogue.ddos.z_score` |
| `drogue.ban.issued` | Counter | attrs `drogue.ban.key`, `drogue.ban.level`, `drogue.ban.duration` |
| `drogue.circuit_breaker.state_change` | Counter | attrs `drogue.circuit_breaker.state`, `drogue.circuit_breaker.key` |

## Configuration

```python
from drogue.observability.opentelemetry import DrogueTelemetry

telemetry = DrogueTelemetry(service_name="my-api")
```
