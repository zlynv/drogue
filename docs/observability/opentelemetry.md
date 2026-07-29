# OpenTelemetry

## Setup

```bash
pip install drogue[opentelemetry]
```

```python
from drogue.observability.opentelemetry import DrogueTelemetry

telemetry = DrogueTelemetry(
    service_name="my-api",
    enable_metrics=True,
    enable_tracing=True,
)
```

## Traces

```python
with telemetry.start_span("rate_limit_check") as span:
    span.set_attribute("client_ip", "192.168.1.1")
    span.set_attribute("rate_limit", "10/minute")
    span.set_attribute("result", "allowed")
```

## Metrics

```python
telemetry.record_request_count("allowed")
telemetry.record_request_count("limited")
telemetry.record_rate_limit_time(0.000043)
telemetry.record_active_keys(150)
```

## Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `drogue.client_ip` | string | Client IP address |
| `drogue.rate_limit` | string | Rate limit string |
| `drogue.algorithm` | string | Algorithm used |
| `drogue.result` | string | `allowed` or `limited` |
| `drogue.remaining` | int | Remaining requests |
| `drogue.key` | string | Rate limit key |

## Configuration

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    telemetry_enabled=True,
    telemetry_service_name="my-api",
)
```
