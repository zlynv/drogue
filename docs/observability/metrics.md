# Metrics

## Built-in metrics

| Metric | Type | Description |
|--------|------|-------------|
| `drogue_requests_total` | Counter | Total requests processed |
| `drogue_allowed_total` | Counter | Allowed requests |
| `drogue_limited_total` | Counter | Rate-limited requests |
| `drogue_rate_limit_seconds` | Histogram | Per-request processing time |
| `drogue_active_keys` | Gauge | Keys in storage |
| `drogue_trust_transitions_total` | Counter | Trust state changes |
| `drogue_bans_total` | Counter | Bans issued |
| `drogue_detections_total` | Counter | Anomalies detected |
| `drogue_circuit_breaker_trips_total` | Counter | Circuit breaker trips |

## Prometheus endpoint

```python
from drogue.observability.metrics import DrogueMetrics

metrics = DrogueMetrics()

@app.get("/metrics")
async def metrics_endpoint():
    return Response(
        content=metrics.export_prometheus(),
        media_type="text/plain",
    )
```

## Recording

```python
metrics.record_request("allowed")
metrics.record_request("limited")
metrics.record_rate_limit_time(0.000043)
metrics.record_trust_transition("unknown", "normal")
metrics.record_ban("192.168.1.1")
metrics.record_detection("192.168.1.1", "ddos")
metrics.record_circuit_breaker_trip()
```

## Export

```python
# Prometheus format
output = metrics.export_prometheus()

# JSON
output = metrics.export_json()
```
