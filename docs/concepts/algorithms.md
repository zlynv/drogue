---
description: Rate limiting algorithms explained with visual examples. Token Bucket, Sliding Window, Fixed Window, GCRA, and Leaky Bucket.
---

# Algorithms

drogue provides five rate limiting algorithms. Each has different trade-offs for burst handling, accuracy, and memory usage.

## Token Bucket

### What it is

A bucket holds tokens that refill at a steady rate. Each request consumes tokens. When the bucket is empty, requests are denied. Allows bursts up to the bucket capacity.

### How it works

```
Time 0s:   Bucket = [■■■■■■■■■■] (10 tokens, full)
Time 1s:   Request arrives, consumes 1 → [■■■■■■■■■□] (9 left)
Time 2s:   Request arrives, consumes 1 → [■■■■■■■■□□] (8 left)
Time 3s:   2 tokens refill → [■■■■■■■■■■] (10 again)
Time 4s:   5 requests arrive fast → [■■■■■□□□□□] (5 left)
            All 5 allowed (burst tolerance)
Time 5s:   3 more requests → denied (only 5 left, need 3... wait)
```

### Visual example

```
Rate: 10 requests/minute, bucket capacity: 10

Time:  0s   10s   20s   30s   40s   50s   60s
       |     |     |     |     |     |     |
Tokens: 10 → 10 → 10 →  5 →  5 →  8 → 10
              ↑           ↑     ↑
           refill      5 req   3 req
                      (burst)  (refill)
```

### When to use

- APIs that allow occasional bursts (batch operations, page loads)
- Default choice for most applications
- When you want smooth rate limiting with burst tolerance

### Example

```python
from drogue.core.algorithms import TokenBucketAlgorithm
from drogue.core.storage.memory import MemoryStorage

storage = MemoryStorage()
await storage.initialize()

# 100 requests per minute, bucket refills steadily
algorithm = TokenBucketAlgorithm(storage=storage, limit=100, window=60.0)

# Burst: 10 requests instantly — all allowed
for i in range(10):
    result = await algorithm.acquire("user123")
    print(f"Request {i+1}: allowed={result.allowed}, remaining={result.remaining}")
# Request 1: allowed=True, remaining=9
# Request 2: allowed=True, remaining=8
# ...
# Request 10: allowed=True, remaining=0

# 11th request: denied (bucket empty)
result = await algorithm.acquire("user123")
print(f"Request 11: allowed={result.allowed}, retry_after={result.retry_after:.1f}s")
# Request 11: allowed=False, retry_after=0.6s

# Wait 0.6s, tokens refill
import asyncio
await asyncio.sleep(0.6)
result = await algorithm.acquire("user123")
print(f"After wait: allowed={result.allowed}, remaining={result.remaining}")
# After wait: allowed=True, remaining=0
```

### Real-world scenario

```python
# API endpoint: 1000 requests/hour per user
# User uploads a CSV with 500 rows → 500 requests in 10 seconds
# Token Bucket allows this burst (500 < 1000 capacity)
# After burst, user must wait for refill

@limiter.limit("1000/hour", algorithm=AlgorithmType.TOKEN_BUCKET)
async def process_csv():
    # 500 rows processed in burst — allowed
    ...
```

---

## Sliding Window Counter

### What it is

Estimates the count in the current window by combining the previous and current window counts with a weighted formula. Eliminates the "boundary burst" problem of fixed windows.

### How it works

```
Window size: 60 seconds
Limit: 100 requests

Previous window (12:00-12:01): 80 requests
Current window (12:01-now, 20 seconds elapsed):

estimated_count = 80 × ((60 - 20) / 60) + current_count
                = 80 × 0.667 + current_count
                = 53.3 + current_count

If current_count < 47 → allowed (53.3 + 47 = 100.3 ≈ limit)
```

### Visual example

```
Rate: 100 requests/minute

Previous Window     Current Window (20s elapsed)
[■■■■■■■■■■■■■■■■□□□□] [■■■■□□□□□□□□□□□□□□□□]
      80/100                  20/100

Weighted: 80 × (40/60) + 20 = 53.3 + 20 = 73.3
Remaining: 100 - 73 = 27 requests allowed
```

### When to use

- Strict rate limiting where boundary bursts are unacceptable
- APIs that need accurate counting across window boundaries
- When you can tolerate slightly more memory (2 counters per key)

### Example

```python
from drogue.core.algorithms import SlidingWindowAlgorithm

algorithm = SlidingWindowAlgorithm(storage=storage, limit=100, window=60.0)

# 12:00:00 — send 100 requests (all allowed)
for i in range(100):
    result = await algorithm.acquire("user123")
# All allowed

# 12:00:30 — 30 seconds later
# Previous window: 100, current window: 0
# estimated = 100 × ((60-30)/60) + 0 = 50
result = await algorithm.acquire("user123")
print(f"30s later: allowed={result.allowed}, remaining={result.remaining}")
# 30s later: allowed=True, remaining=49
# Allowed because estimated count (50) < limit (100)

# 12:00:45 — 45 seconds later
# estimated = 100 × ((60-45)/60) + 0 = 25
result = await algorithm.acquire("user123")
print(f"45s later: allowed={result.allowed}, remaining={result.remaining}")
# 45s later: allowed=True, remaining=74
```

### Real-world scenario

```python
# Login endpoint: 5 attempts per minute
# User tries at 12:00:55 (5 attempts), then at 12:01:05 (1 attempt)

# Fixed Window: Would allow 5 more at 12:01:05 (new window)
# Sliding Window: Only allows 0-1 (weighted estimate still high)

@limiter.limit("5/minute", algorithm=AlgorithmType.SLIDING_WINDOW)
async def login():
    # Sliding window prevents boundary abuse
    ...
```

---

## Fixed Window Counter

### What it is

The simplest algorithm. Counts requests in fixed time windows (e.g., 12:00-12:01, 12:01-12:02). When the window resets, the counter resets to zero.

### How it works

```
Window 1: 12:00:00 - 12:01:00
  Count: 0 → 1 → 2 → ... → 100 → DENIED

Window 2: 12:01:00 - 12:02:00
  Count: 0 → 1 → 2 → ... → 100 → DENIED
```

### Visual example

```
Rate: 100 requests/minute

Time:  12:00:00    12:01:00    12:02:00
       |            |            |
       v            v            v
Window: [■■■■■■■■■■] [■■■■■■■■■■] [■■■■■■■■■■]
        100 allowed   100 allowed   100 allowed

⚠️ Boundary problem:
12:00:59 → 100 requests
12:01:01 → 100 requests
= 200 requests in 2 seconds!
```

### When to use

- Development/testing environments
- Simple rate limiting where boundary bursts don't matter
- When you need minimum memory usage (1 counter per key)

### Example

```python
from drogue.core.algorithms import FixedWindowAlgorithm

algorithm = FixedWindowAlgorithm(storage=storage, limit=100, window=60.0)

# Window: 12:00:00 - 12:01:00
for i in range(100):
    result = await algorithm.acquire("user123")
# All allowed

# Request 101: denied
result = await algorithm.acquire("user123")
print(f"Request 101: allowed={result.allowed}")
# Request 101: allowed=False

# Window: 12:01:00 - 12:02:00
# Counter resets to 0
result = await algorithm.acquire("user123")
print(f"New window: allowed={result.allowed}, remaining={result.remaining}")
# New window: allowed=True, remaining=99
```

### Real-world scenario

```python
# Simple API: 1000 requests/hour
# Boundary bursts acceptable (most traffic is spread out)

@limiter.limit("1000/hour", algorithm=AlgorithmType.FIXED_WINDOW)
async def get_data():
    # Simple, low memory, good enough for most cases
    ...
```

---

## GCRA (Generic Cell Rate Algorithm)

### What it is

A cell-based algorithm from telecom (ATM networks). Evenly spaces requests with no bursts allowed. Each request has a "theoretical arrival time" (TAT) — the earliest time the next request can arrive.

### How it works

```
emission_interval = window / limit  (time between allowed requests)
burst = limit                       (maximum burst size)

For each request:
  new_tat = max(previous_tat, now) + emission_interval
  allow_at = new_tat - burst × emission_interval

  if allow_at ≤ now → allowed
  else → denied (wait until allow_at)
```

### Visual example

```
Rate: 10 requests/minute → emission_interval = 6 seconds

Time:  0s    6s    12s   18s   24s   30s
       |     |     |     |     |     |
       ✓     ✓     ✓     ✓     ✓     ✓
       ↑     ↑     ↑     ↑     ↑     ↑
    evenly spaced, 6 seconds apart

Burst attempt at t=0:
  5 requests at once → only 1 allowed (rest denied)
  Next allowed at t=6s
```

### When to use

- APIs requiring perfectly smooth traffic
- Telecom or streaming systems
- When bursts cause problems (rate-limited third-party APIs)

### Example

```python
from drogue.core.algorithms import GCRAAlgorithm

# 10 requests/minute, emission interval = 6 seconds
algorithm = GCRAAlgorithm(storage=storage, limit=10, window=60.0)

# Request 1: allowed (TAT = now + 6s)
result = await algorithm.acquire("user123")
print(f"Request 1: allowed={result.allowed}")
# Request 1: allowed=True

# Request 2 immediately: denied (TAT = now + 12s, allow_at = now + 6s)
result = await algorithm.acquire("user123")
print(f"Request 2: allowed={result.allowed}, retry_after={result.retry_after:.1f}s")
# Request 2: allowed=False, retry_after=6.0s

# Wait 6 seconds
import asyncio
await asyncio.sleep(6)

# Request 2: allowed (TAT updated)
result = await algorithm.acquire("user123")
print(f"After 6s: allowed={result.allowed}")
# After 6s: allowed=True
```

### Real-world scenario

```python
# Third-party API: strict 100 requests/minute, no bursts allowed
# GCRA ensures you never exceed, even temporarily

@limiter.limit("100/minute", algorithm=AlgorithmType.GCRA)
async def call_external_api():
    # Smooth traffic, no bursts, safe for strict rate limits
    ...
```

---

## Leaky Bucket

### What it is

Requests fill a bucket that leaks at a constant rate. If the bucket is full, new requests are denied (or queued). Different from Token Bucket: Leaky Bucket processes at a constant rate with no bursts.

### How it works

```
Bucket capacity: 10 (same as limit)
Leak rate: 10/60 = 0.167 requests/second

Time 0s: Bucket = 0 (empty)
  → 5 requests arrive → Bucket = 5 (all allowed)

Time 1s: Bucket leaks 0.167 → Bucket = 4.83
  → 3 requests arrive → Bucket = 7.83 (all allowed)

Time 2s: Bucket leaks 0.167 → Bucket = 7.66
  → 5 requests arrive → Bucket would be 12.66 > capacity(10)
  → 2 denied, 3 allowed
```

### Visual example

```
Rate: 10 requests/minute, capacity: 10

Time:  0s    10s   20s   30s   40s   50s   60s
       |     |     |     |     |     |     |
Water: 0 →   3 →   5 →   4 →   6 →   3 →   0
       ↑     ↑     ↑     ↑     ↑     ↑     ↑
    fill  leak  fill  leak  fill  leak  leak
```

### When to use

- APIs requiring constant-rate processing
- Queue-based systems (job queues, task processors)
- When you need to smooth out traffic spikes

### Example

```python
from drogue.core.algorithms import LeakyBucketAlgorithm

# 10 requests/minute, bucket capacity 10
algorithm = LeakyBucketAlgorithm(storage=storage, limit=10, window=60.0)

# Burst: 5 requests instantly
for i in range(5):
    result = await algorithm.acquire("user123")
    print(f"Request {i+1}: allowed={result.allowed}, water={10 - result.remaining}")
# Request 1: allowed=True, water=1
# Request 2: allowed=True, water=2
# ...
# Request 5: allowed=True, water=5

# 6 more requests (bucket would overflow)
for i in range(6):
    result = await algorithm.acquire("user123")
    if not result.allowed:
        print(f"Request {i+6}: denied, retry_after={result.retry_after:.1f}s")
        break
# Request 6: denied, retry_after=6.0s
```

### Real-world scenario

```python
# Job queue: process at most 10 jobs/minute
# Leaky Bucket ensures constant processing rate
# Bursts are queued, not processed immediately

@limiter.limit("10/minute", algorithm=AlgorithmType.LEAKY_BUCKET)
async def process_job():
    # Constant rate, no bursts, smooth processing
    ...
```

---

## Algorithm comparison

| Feature | Token Bucket | Sliding Window | Fixed Window | GCRA | Leaky Bucket |
|---------|-------------|----------------|--------------|------|--------------|
| **Bursts** | Yes (up to capacity) | No | At boundaries | No | No |
| **Accuracy** | Good | Best | Good (except boundaries) | Good | Good |
| **Memory** | 2 values/key | 2 counters/key | 1 counter/key | 1 value/key | 2 values/key |
| **Complexity** | Low | Medium | Low | Low | Low |
| **Use case** | Most APIs | Strict rate limiting | Simple cases | Smooth traffic | Constant rate |
| **Best for** | General purpose | Login/security | Development | Third-party APIs | Job queues |

## Choosing an algorithm

```python
from drogue.core.algorithms import (
    TokenBucketAlgorithm,
    SlidingWindowAlgorithm,
    FixedWindowAlgorithm,
    GCRAAlgorithm,
    LeakyBucketAlgorithm,
)

# Default: Token Bucket (good for most cases)
@limiter.limit("100/minute", algorithm=AlgorithmType.TOKEN_BUCKET)

# Strict: Sliding Window (no bursts, most accurate)
@limiter.limit("100/minute", algorithm=AlgorithmType.SLIDING_WINDOW)

# Simple: Fixed Window (lowest memory)
@limiter.limit("100/minute", algorithm=AlgorithmType.FIXED_WINDOW)

# Smooth: GCRA (evenly spaced, no bursts)
@limiter.limit("100/minute", algorithm=AlgorithmType.GCRA)

# Constant: Leaky Bucket (smooth processing)
@limiter.limit("100/minute", algorithm=AlgorithmType.LEAKY_BUCKET)
```

## Common methods

All algorithms share these methods:

| Method | Signature | Description |
|--------|-----------|-------------|
| `acquire` | `(key, cost=1, block=False, timeout=None)` | Try to acquire a slot |
| `peek` | `(key)` | Check state without consuming |
| `reset` | `(key)` | Reset a key's state |

## Blocking mode

Instead of denying immediately, wait for a slot:

```python
# Wait up to 5 seconds for a slot
result = await algorithm.acquire("user123", block=True, timeout=5.0)

# If allowed immediately:
# AcquireResult(allowed=True, remaining=9, ...)

# If waited and got a slot:
# AcquireResult(allowed=True, remaining=0, ...)

# If timeout exceeded:
# AcquireResult(allowed=False, retry_after=3.2, ...)
```
