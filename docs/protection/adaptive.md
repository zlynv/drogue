# Adaptive Rate Limiting

## How it works

1. Monitor system metrics (CPU, memory, event loop latency)
2. Calculate load factor from metrics
3. Scale rate limits down when load is high

**Formula:**

```
scaled_limit = base_limit * (1.0 - load_factor * scale_factor)
```

## Enable

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    adaptive_enabled=True,
    adaptive_scale_factor=0.5,
    adaptive_cpu_threshold=0.8,
    adaptive_memory_threshold=0.8,
    adaptive_check_interval=5.0,
)
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `adaptive_enabled` | `False` | Enable adaptive limiting |
| `adaptive_scale_factor` | `0.5` | Max scale-down factor (0-1) |
| `adaptive_cpu_threshold` | `0.8` | CPU threshold to trigger scaling |
| `adaptive_memory_threshold` | `0.8` | Memory threshold to trigger scaling |
| `adaptive_check_interval` | `5.0` | Metrics check interval (seconds) |

## Standalone usage

```python
from drogue.protection.adaptive import AdaptiveRateLimiter

limiter = AdaptiveRateLimiter(scale_factor=0.5, check_interval=5.0)

# Get current metrics
metrics = limiter.get_metrics()
# {"cpu_percent": 65.2, "memory_percent": 72.1, "event_loop_latency": 0.012}

# Get adaptive limit
limit = limiter.get_adaptive_limit(base_limit=1000)
# 850 (if load is moderate)

# Check if system is loaded
if limiter.is_system_loaded():
    print("System under load")
```

## Scaling behavior

| CPU/Memory | Scale factor | Effective limit (base=1000) |
|------------|--------------|------------------------------|
| 0-80% | 1.0 | 1000 |
| 80-90% | 0.75 | 750 |
| 90-95% | 0.5 | 500 |
| 95%+ | 0.25 | 250 |
