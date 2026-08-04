# Metrics

## What is metrics collection?

Metrics collection tracks your rate limiter's behavior in real-time. It counts requests, bans, anomalies, and other events. This data is essential for monitoring, alerting, and understanding your API's traffic patterns.

## Usage

```python
from drogue.observability.metrics import DrogueMetrics

metrics = DrogueMetrics(max_routes=500)

# Record events
metrics.record_allowed(route="/api/data")      # Request was allowed
metrics.record_rejected(route="/api/data")     # Request was rate limited
metrics.record_check_latency(0.000043)         # 43 microseconds
metrics.record_ban("192.168.1.1", level=1)     # Client banned
metrics.record_ban_expired()                    # Ban expired
metrics.record_ddos_detection("192.168.1.1")  # DDoS detected
metrics.record_circuit_trip()                   # Circuit breaker opened
metrics.record_circuit_reset()                  # Circuit breaker recovered

# Export
prometheus_output = metrics.to_prometheus()    # Prometheus text format
summary = metrics.get_summary()                # Dict with all counts
```

## Response examples

### `get_summary()` response

```python
summary = metrics.get_summary()
# {
#     "requests_allowed": 15000,
#     "requests_rejected": 500,
#     "total_requests": 15500,
#     "rejection_rate": 0.032,
#     "bans_total": 25,
#     "bans_active": 5,
#     "ddos_detections": 3,
#     "circuit_trips": 2,
#     "circuit_resets": 1,
#     "avg_latency_us": 43.0,
# }
```

### `to_prometheus()` response

```
# HELP drogue_requests_allowed_total Total allowed requests
# TYPE drogue_requests_allowed_total counter
drogue_requests_allowed_total 15000

# HELP drogue_requests_rejected_total Total rejected requests
# TYPE drogue_requests_rejected_total counter
drogue_requests_rejected_total 500

# HELP drogue_bans_total Total bans issued
# TYPE drogue_bans_total counter
drogue_bans_total 25

# HELP drogue_bans_active Currently active bans
# TYPE drogue_bans_active gauge
drogue_bans_active 5

# HELP drogue_ddos_detections_total DDoS detections
# TYPE drogue_ddos_detections_total counter
drogue_ddos_detections_total 3

# HELP drogue_circuit_trips_total Circuit breaker trips
# TYPE drogue_circuit_trips_total counter
drogue_circuit_trips_total 2
```

## Configuration

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    metrics_enabled=True,
)
```

## Prometheus integration

```python
from fastapi import FastAPI, Response
from drogue.observability.metrics import DrogueMetrics

app = FastAPI()
metrics = DrogueMetrics()

@app.get("/metrics")
async def metrics_endpoint():
    return Response(
        content=metrics.to_prometheus(),
        media_type="text/plain",
    )
```
