# Adaptive Rate Limiting

## Overview

Adaptive Rate Limiting dynamically adjusts rate limits based on system metrics like CPU usage, memory pressure, and request latency.

## Usage

```python
from drogue.protection.adaptive import AdaptiveRateLimiter

adaptive = AdaptiveRateLimiter(
    cpu_threshold=0.8,      # Reduce when CPU > 80%
    memory_threshold=0.8,   # Reduce when memory > 80%
    latency_threshold=1.0,  # Reduce when p95 > 1s
    check_interval=5.0,     # Check every 5 seconds
)

# Get effective limit
effective_limit = adaptive.get_effective_limit(base_limit=100)
# Returns reduced limit when system is under pressure
```

## Configuration

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    adaptive_enabled=True,
    adaptive_cpu_threshold=0.8,
    adaptive_memory_threshold=0.8,
    adaptive_latency_threshold=1.0,
    adaptive_check_interval=5.0,
)
```

## How It Works

1. Monitor system metrics periodically
2. Compute reduction factor for each metric
3. Apply combined reduction to base limit
4. Never reduce below 1 request

**Reduction formula:**

```
If metric > threshold:
    excess = (metric - threshold) / (1.0 - threshold)
    reduction = max(0.1, 1.0 - (excess * 0.9))
Else:
    reduction = 1.0
```

## Metrics Monitored

| Metric | Threshold | Reduction |
|--------|-----------|-----------|
| CPU usage | 80% | Linear from 1.0 to 0.1 |
| Memory usage | 80% | Linear from 1.0 to 0.1 |
| P95 latency | 1.0s | Proportional to exceedance |

## Recording Latency

```python
import time

# Record request latency
start = time.monotonic()
# ... process request
latency = time.monotonic() - start
adaptive.record_latency(latency)
```

## Getting Metrics

```python
metrics = adaptive.get_metrics()
# {
#     "cpu_usage": 0.45,
#     "memory_usage": 0.62,
#     "cpu_threshold": 0.8,
#     "memory_threshold": 0.8,
#     "cpu_reduction": 1.0,
#     "memory_reduction": 1.0,
#     "latency_reduction": 0.85,
#     "latency_p50": 0.12,
#     "latency_p95": 0.45,
#     "latency_p99": 0.89,
#     "latency_samples": 500,
# }
```

## Dependencies

Adaptive rate limiting requires `psutil`:

```bash
pip install drogue[adaptive]
```

If `psutil` is not installed, only latency-based adjustments are applied.

## Use Cases

- **Auto-scaling:** Reduce limits when system is under load
- **Cloud deployments:** Adapt to variable instance performance
- **Traffic spikes:** Automatically tighten during overload
- **Resource monitoring:** Adjust based on real-time metrics
