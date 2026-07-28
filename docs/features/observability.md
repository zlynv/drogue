# Observability

## Overview

drogue provides three observability mechanisms: Prometheus metrics, OpenTelemetry tracing, and structured logging.

## Prometheus Metrics

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(metrics_enabled=True)
limiter = DrogueLimiter(app, config=config)

@app.get("/metrics")
async def metrics():
    from drogue.observability.metrics import get_metrics
    return get_metrics()
```

**Available metrics:**

- `drogue_rate_limit_requests_total` -- Total rate limit requests
- `drogue_rate_limit_blocked_total` -- Total blocked requests
- `drogue_rate_limit_latency_seconds` -- Rate limit check latency
- `drogue_ddos_detected_total` -- DDoS attacks detected
- `drogue_ban_issued_total` -- Bans issued
- `drogue_circuit_breaker_state_change_total` -- Circuit breaker state changes

## OpenTelemetry

```python
pip install drogue[opentelemetry]

from drogue.observability.opentelemetry import DrogueTelemetry

telemetry = DrogueTelemetry(service_name="my-api")

# Trace rate limit checks
with telemetry.trace_rate_limit_check(key="192.168.1.1", limit=100):
    result = await limiter._check(key, rule)

# Record metrics
telemetry.record_rate_limit_result(allowed=True, route="/api/data")
telemetry.record_latency(latency=0.001, route="/api/data")
telemetry.record_ddos_detected(client_key="192.168.1.1", z_score=4.2)
telemetry.record_ban_issued(key="192.168.1.1", level=1, duration=60)
```

**Available instruments:**

- `drogue.rate_limit.requests` -- Counter for rate limit requests
- `drogue.rate_limit.blocked` -- Counter for blocked requests
- `drogue.rate_limit.latency` -- Histogram for check latency
- `drogue.ddos.detected` -- Counter for DDoS detections
- `drogue.ban.issued` -- Counter for bans issued
- `drogue.circuit_breaker.state_change` -- Counter for state changes

## Structured Logging

```python
import logging
logging.basicConfig(level=logging.INFO)
```

**Log format:**

```json
{
  "event": "rate_limit_allowed",
  "route": "/api/data",
  "key": "192.168.1.1",
  "limit": 10,
  "remaining": 9
}
```

**Available events:**

- `rate_limit_allowed` -- Request allowed
- `rate_limit_rejected` -- Request rejected
- `rate_limit_shadow` -- Shadow mode (would have blocked)
- `ban_issued` -- Ban issued
- `ban_cleared` -- Ban cleared
- `ddos_detected` -- DDoS attack detected
- `probe_detected` -- Probe pattern detected
- `circuit_breaker_open` -- Circuit breaker opened
- `circuit_breaker_closed` -- Circuit breaker closed

## Integration

### Datadog

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    metrics_enabled=True,
    logging_enabled=True,
    log_level="info",
)
```

### Grafana

Use Prometheus metrics endpoint:

```python
@app.get("/metrics")
async def metrics():
    from drogue.observability.metrics import get_metrics
    return get_metrics()
```

### ELK Stack

Structured JSON logs are automatically parsed by Logstash.
