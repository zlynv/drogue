# Algorithms

## Token Bucket

The default algorithm. Burst-friendly with steady refill.

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(default_algorithm="token_bucket")
```

**How it works:**

- Bucket fills at a steady rate (e.g., 1 token per second)
- Each request consumes tokens
- Bursts are allowed up to the bucket capacity
- After burst, refill rate determines when more requests are allowed

**Best for:**

- APIs with bursty traffic
- Endpoints that need to handle occasional spikes
- User-facing applications

**Trade-off:**

- Allows bursts (can be good or bad)
- Slightly higher memory per key

## Sliding Window

Most accurate algorithm with no boundary burst issues.

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(default_algorithm="sliding_window")
```

**How it works:**

- Tracks requests in a sliding time window
- Counts requests from `now - window` to `now`
- No boundary burst issues (unlike Fixed Window)

**Best for:**

- APIs requiring strict rate limiting
- Financial or security-sensitive endpoints
- When accuracy is more important than performance

**Trade-off:**

- Most accurate
- Slightly higher memory usage
- No burst allowance

## Fixed Window

Simplest algorithm with lowest overhead.

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(default_algorithm="fixed_window")
```

**How it works:**

- Divides time into fixed windows (e.g., 1-minute windows)
- Counts requests within each window
- Resets counter at window boundary

**Best for:**

- Simple use cases
- When performance is critical
- When boundary burst is acceptable

**Trade-off:**

- Simplest implementation
- Lowest memory usage
- May allow up to 2x burst at window boundaries

## Comparison

| Algorithm | Accuracy | Memory | Burst | Best For |
|-----------|----------|--------|-------|----------|
| Token Bucket | High | Medium | Allowed | General APIs |
| Sliding Window | Highest | High | None | Strict limiting |
| Fixed Window | Medium | Low | At boundaries | Simple use cases |

## Per-Route Algorithm

You can override the algorithm per route:

```python
from drogue.core.rules.rule import AlgorithmType

@app.get("/api/strict")
@limiter.limit("10/minute", algorithm=AlgorithmType.SLIDING_WINDOW)
async def strict_endpoint():
    return {"data": "value"}

@app.get("/api/burst")
@limiter.limit("100/minute", algorithm=AlgorithmType.TOKEN_BUCKET)
async def burst_endpoint():
    return {"data": "value"}
```
