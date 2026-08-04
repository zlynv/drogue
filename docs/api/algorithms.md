# Algorithms API

## TokenBucketAlgorithm

```python
from drogue.core.algorithms.token_bucket import TokenBucketAlgorithm
from drogue.core.storage.memory import MemoryStorage

storage = MemoryStorage()
algorithm = TokenBucketAlgorithm(storage=storage, limit=100, window=60.0)

result = await algorithm.acquire("user123", cost=1)
# AcquireResult(allowed=True, remaining=99, limit=100, reset_at=1690000060.0)

result = await algorithm.peek("user123")
await algorithm.reset("user123")
```

## SlidingWindowAlgorithm

```python
from drogue.core.algorithms.sliding_window import SlidingWindowAlgorithm

algorithm = SlidingWindowAlgorithm(storage=storage, limit=100, window=60.0)

result = await algorithm.acquire("user123")
```

## FixedWindowAlgorithm

```python
from drogue.core.algorithms.fixed_window import FixedWindowAlgorithm

algorithm = FixedWindowAlgorithm(storage=storage, limit=100, window=60.0)

result = await algorithm.acquire("user123")
```

## GCRAAlgorithm

```python
from drogue.core.algorithms.gcra import GCRAAlgorithm

algorithm = GCRAAlgorithm(storage=storage, limit=100, window=60.0)

result = await algorithm.acquire("user123")
# Smooth, cell-based rate limiting with no bursts.
# Emission interval = window / limit (time between allowed requests)
```

## LeakyBucketAlgorithm

```python
from drogue.core.algorithms.leaky_bucket import LeakyBucketAlgorithm

algorithm = LeakyBucketAlgorithm(storage=storage, limit=100, window=60.0)

result = await algorithm.acquire("user123")
# Processes requests at a constant rate (no bursts).
# Bucket leaks at limit/window per second.
```

## Common methods

All algorithms share:

| Method | Signature | Description |
|--------|-----------|-------------|
| `acquire` | `(key: str, cost: int = 1, block: bool = False, timeout: float \| None = None) -> AcquireResult` | Try to acquire a slot |
| `peek` | `(key: str) -> AcquireResult` | Check without consuming |
| `reset` | `(key: str) -> None` | Reset a key's state |

## AcquireResult

```python
@dataclass
class AcquireResult:
    allowed: bool          # Whether request is allowed
    remaining: int         # Remaining requests in window
    limit: int             # Max requests allowed
    retry_after: float     # Seconds to wait (0 if allowed)
    reset_at: float        # Unix timestamp when window resets (optional)

    @property
    def headers(self) -> dict[str, str]:
        # Auto-generated rate limit headers:
        # X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset, Retry-After
```

## AlgorithmType enum

```python
from drogue.core.rules.rule import AlgorithmType

AlgorithmType.TOKEN_BUCKET    # "token_bucket"
AlgorithmType.SLIDING_WINDOW  # "sliding_window"
AlgorithmType.FIXED_WINDOW    # "fixed_window"
AlgorithmType.GCRA            # "gcra" (Generic Cell Rate Algorithm)
AlgorithmType.LEAKY_BUCKET    # "leaky_bucket"
```
