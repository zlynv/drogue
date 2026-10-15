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
#     "bans_total": 25,
#     "bans_active": 5,
#     "ddos_detections": 3,
#     "circuit_trips": 2,
#     "circuit_state": 0.0,
#     "check_latency_avg": 0.000043,
#     "check_latency_count": 15500,
# }
```

### `to_prometheus()` response

```
# HELP drogue_requests_total Total rate limit checks
# TYPE drogue_requests_total counter
drogue_requests_total{status="allowed"} 15000
drogue_requests_total{status="rejected"} 500

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

# HELP drogue_check_latency_seconds Rate limit check latency
# TYPE drogue_check_latency_seconds summary
drogue_check_latency_seconds_count 15500
drogue_check_latency_seconds_sum 0.665000

# HELP drogue_route_requests_total Per-route request counts
# TYPE drogue_route_requests_total counter
drogue_route_requests_total{route="/api/data",status="allowed"} 15000
drogue_route_requests_total{route="/api/data",status="rejected"} 500
```

Per-route series are capped by `max_routes` (default 500): lowest-traffic
routes are evicted first. The latency export is a `_count`/`_sum` pair;
per-bucket histograms are not exported.

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
