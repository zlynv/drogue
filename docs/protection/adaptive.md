# Adaptive Rate Limiting

## What is adaptive rate limiting?

Adaptive rate limiting adjusts rate limits based on system load. When your server is under heavy load (high CPU, memory, or latency), drogue automatically reduces rate limits to protect the system. When load returns to normal, limits are restored.

## How it works

```
1. Monitor system metrics (CPU, memory, event loop latency)
2. Calculate a load factor (0.0 = no load, 1.0 = max load)
3. Scale rate limits down based on load:
   scaled_limit = base_limit * (1.0 - load_factor * scale_factor)
4. When load is high, limits decrease
5. When load is normal, limits are restored
```

## Usage

```python
from drogue.protection.adaptive import AdaptiveRateLimiter

limiter = AdaptiveRateLimiter(
    cpu_threshold=0.8,        # CPU threshold to start scaling
    memory_threshold=0.8,     # Memory threshold to start scaling
    latency_threshold=1.0,    # Event loop latency threshold (seconds)
    check_interval=5.0,       # How often to check metrics
)

# Get effective limit under current load
effective = limiter.get_effective_limit(base_limit=1000)
# 850 (if CPU is at 85%, limits reduced by 15%)

# Record latency for adaptive scaling
limiter.record_latency(0.05)  # 50ms request latency

# Get current metrics
metrics = limiter.get_metrics()
# {
#     "cpu_percent": 65.2,
#     "memory_percent": 72.1,
#     "event_loop_latency": 0.012,
#     "effective_scale": 0.85,
#     "base_limit": 1000,
#     "effective_limit": 850,
# }
```

## Response examples

### `get_effective_limit()` response

```python
# Normal load (CPU 50%)
limit = limiter.get_effective_limit(1000)
# 1000  (no reduction)

# High load (CPU 85%)
limit = limiter.get_effective_limit(1000)
# 825   (17.5% reduction)

# Critical load (CPU 95%)
limit = limiter.get_effective_limit(1000)
# 500   (50% reduction)
```

### `get_metrics()` response

```python
metrics = limiter.get_metrics()
# {
#     "cpu_percent": 65.2,           # Current CPU usage
#     "memory_percent": 72.1,        # Current memory usage
#     "event_loop_latency": 0.012,   # Async event loop latency (seconds)
#     "scale_factor": 0.5,           # Configured scale factor
#     "cpu_threshold": 0.8,          # CPU threshold
#     "memory_threshold": 0.8,       # Memory threshold
# }
```

## Scaling behavior

| CPU/Memory | Load Factor | Effective Limit (base=1000) |
|------------|-------------|------------------------------|
| 0-80% | 0.0 | 1000 |
| 85% | 0.25 | 750 |
| 90% | 0.5 | 500 |
| 95% | 0.75 | 250 |
| 100% | 1.0 | 0 (all blocked) |

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
