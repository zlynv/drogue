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

## DrogueLogger

```python
from drogue.observability.logging import DrogueLogger

logger = DrogueLogger(
    level="INFO",
    json_format=True,
    include_client_ip=True,
    include_request_path=True,
    include_rate_limit_info=True,
)
```

## DrogueTelemetry

```python
from drogue.observability.opentelemetry import DrogueTelemetry

telemetry = DrogueTelemetry(
    service_name="my-api",
    enable_metrics=True,
    enable_tracing=True,
)

# Traces
with telemetry.start_span("rate_limit_check") as span:
    span.set_attribute("client_ip", "192.168.1.1")

# Metrics
telemetry.record_request_count("allowed")
telemetry.record_rate_limit_time(0.000043)
telemetry.record_active_keys(150)
```
