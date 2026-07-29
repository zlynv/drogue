# Algorithms

drogue provides three rate limiting algorithms. Each has different trade-offs for burst handling, accuracy, and memory usage.

## Token Bucket

### What it is

A bucket holds tokens that refill at a steady rate. Each request consumes tokens. When the bucket is empty, requests are denied.

### How it works

```
1. Bucket starts full (e.g., 100 tokens)
2. Each request consumes 1 token
3. Tokens refill at a steady rate (e.g., 100/minute = 1.67/second)
4. If tokens remain, request is allowed
5. If bucket is empty, request is denied
```

### When to use

- APIs that allow occasional bursts (e.g., a spike during batch operations)
- When you want smooth rate limiting with burst tolerance
- Most common choice -- good default

### Example

```python
from drogue.core.algorithms.token_bucket import TokenBucketAlgorithm
from drogue.core.storage.memory import MemoryStorage

storage = MemoryStorage()
await storage.initialize()

# 100 requests per minute, bucket refills steadily
algorithm = TokenBucketAlgorithm(storage=storage, limit=100, window=60.0)

# Request 1: allowed (99 tokens left)
result = await algorithm.acquire("user123")
# AcquireResult(allowed=True, remaining=99, limit=100, reset=1690000060.0, retry_after=0)

# Request 2: allowed (98 tokens left)
result = await algorithm.acquire("user123")
# AcquireResult(allowed=True, remaining=98, limit=100, reset=1690000060.0, retry_after=0)

# Exhaust tokens
for i in range(98):
    await algorithm.acquire("user123")

# Request 101: denied (0 tokens)
result = await algorithm.acquire("user123")
# AcquireResult(allowed=False, remaining=0, limit=100, reset=1690000060.0, retry_after=45.2)
```

### Storage format

```
Key: "tb:user123"
Value: (remaining_tokens: float, last_refill_time: float)
Example: (99.5, 1690000015.0)
```

### Response fields

| Field | Description |
|-------|-------------|
| `allowed` | `True` if request is allowed, `False` if denied |
| `remaining` | Number of tokens left in the bucket |
| `limit` | Maximum tokens (the rate limit) |
| `reset` | Unix timestamp when the bucket refills |
| `retry_after` | Seconds to wait before next allowed request (0 if allowed) |

---

## Sliding Window Counter

### What it is

Estimates the count in the current window by combining the previous and current window counts with a weighted formula. This eliminates the "boundary burst" problem of fixed windows.

### How it works

```
1. Track request counts in fixed time windows (e.g., 1-minute windows)
2. When a request arrives, calculate the weighted count:
   estimated_count = prev_count * ((window - elapsed) / window) + curr_count
3. If estimated_count < limit, allow the request
4. Otherwise, deny it
```

### Why it's better than fixed window

Fixed windows have a boundary problem: if you hit the limit at 11:59:59 and again at 12:00:01, you've sent 2x the limit in 2 seconds. Sliding window smooths this out.

### Example

```python
from drogue.core.algorithms.sliding_window import SlidingWindowAlgorithm

algorithm = SlidingWindowAlgorithm(storage=storage, limit=100, window=60.0)

# 10:00:00 - send 100 requests
for i in range(100):
    result = await algorithm.acquire("user123")
# All allowed

# 10:00:30 - 30 seconds into the window
# Previous window had 100, current has 0
# estimated = 100 * ((60 - 30) / 60) + 0 = 50
result = await algorithm.acquire("user123")
# AcquireResult(allowed=True, remaining=49, limit=100, ...)
# Allowed because estimated count (50) < limit (100)
```

### Response fields

Same as Token Bucket: `allowed`, `remaining`, `limit`, `reset`, `retry_after`.

---

## Fixed Window Counter

### What it is

The simplest algorithm. Counts requests in fixed time windows (e.g., 12:00-12:01, 12:01-12:02). When the window resets, the counter resets to zero.

### How it works

```
1. Divide time into fixed windows (e.g., 1-minute windows)
2. Count requests in the current window
3. If count < limit, allow the request
4. Otherwise, deny it
5. When the window ends, reset the counter
```

### When to use

- You need simplicity and low memory
- You can tolerate the boundary burst issue
- Development/testing environments

### Example

```python
from drogue.core.algorithms.fixed_window import FixedWindowAlgorithm

algorithm = FixedWindowAlgorithm(storage=storage, limit=100, window=60.0)

# Window: 12:00:00 - 12:01:00
# Send 100 requests
for i in range(100):
    result = await algorithm.acquire("user123")
# All allowed

# Request 101: denied
result = await algorithm.acquire("user123")
# AcquireResult(allowed=False, remaining=0, limit=100, reset=1690000060.0, retry_after=30.5)

# Window: 12:01:00 - 12:02:00
# Counter resets
result = await algorithm.acquire("user123")
# AcquireResult(allowed=True, remaining=99, limit=100, reset=1690000120.0, retry_after=0)
```

### Boundary burst problem

```
Window 1: 12:00:00 - 12:01:00 (limit: 100)
- Send 100 requests at 12:00:59

Window 2: 12:01:00 - 12:02:00 (limit: 100)
- Send 100 requests at 12:01:01

Result: 200 requests in 2 seconds (12:00:59 - 12:01:01)
```

---

## Algorithm comparison

| Feature | Token Bucket | Sliding Window | Fixed Window |
|---------|-------------|----------------|--------------|
| Bursts | Yes (up to bucket size) | No | At boundaries |
| Accuracy | Good | Best | Good (except boundaries) |
| Memory | 2 values/key | 2 counters/key | 1 counter/key |
| Complexity | Low | Medium | Low |
| Use case | Most APIs | Strict rate limiting | Simple cases |

## Choosing an algorithm

```python
from drogue.core.rules.rule import AlgorithmType

# Default: Token Bucket (good for most cases)
@limiter.limit("100/minute", algorithm=AlgorithmType.TOKEN_BUCKET)

# Strict: Sliding Window (no bursts, most accurate)
@limiter.limit("100/minute", algorithm=AlgorithmType.SLIDING_WINDOW)

# Simple: Fixed Window (lowest memory)
@limiter.limit("100/minute", algorithm=AlgorithmType.FIXED_WINDOW)
```

## Common methods

All algorithms share these methods:

| Method | Signature | Description |
|--------|-----------|-------------|
| `acquire` | `(key: str, cost: int = 1, block: bool = False, timeout: float \| None = None) -> AcquireResult` | Try to acquire a slot |
| `peek` | `(key: str) -> AcquireResult` | Check state without consuming |
| `reset` | `(key: str) -> None` | Reset a key's state |

## Blocking mode

Instead of denying immediately, wait for a slot:

```python
# Wait up to 5 seconds for a slot
result = await algorithm.acquire("user123", block=True, timeout=5.0)

# If allowed immediately:
# AcquireResult(allowed=True, remaining=0, ...)

# If waited and got a slot:
# AcquireResult(allowed=True, remaining=0, ...)

# If timeout exceeded:
# Raises TimeoutError
```
