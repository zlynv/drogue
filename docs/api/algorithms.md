# Algorithms API

## TokenBucket

```python
from drogue.core.algorithms.token_bucket import TokenBucket

bucket = TokenBucket(
    rate=100,
    window=60.0,
    storage=storage,
    key_prefix="tb:",
)

result = await bucket.acquire("user123", cost=1)
# AcquireResult(allowed=True, remaining=99, limit=100, reset=1690000060.0)

result = await bucket.peek("user123")
# AcquireResult(allowed=True, remaining=95, limit=100, reset=1690000060.0)

await bucket.reset("user123")
```

## SlidingWindowCounter

```python
from drogue.core.algorithms.sliding_window import SlidingWindowCounter

window = SlidingWindowCounter(
    limit=100,
    window=60.0,
    storage=storage,
    key_prefix="sw:",
)

result = await window.acquire("user123")
# AcquireResult(allowed=True, remaining=99, limit=100, reset=1690000060.0)
```

## FixedWindowCounter

```python
from drogue.core.algorithms.fixed_window import FixedWindowCounter

window = FixedWindowCounter(
    limit=100,
    window=60.0,
    storage=storage,
    key_prefix="fw:",
)

result = await window.acquire("user123")
# AcquireResult(allowed=True, remaining=99, limit=100, reset=1690000060.0)
```

## AlgorithmType enum

```python
from drogue.core.rules.rule import AlgorithmType

AlgorithmType.TOKEN_BUCKET   # "token_bucket"
AlgorithmType.SLIDING_WINDOW # "sliding_window"
AlgorithmType.FIXED_WINDOW   # "fixed_window"
```

## AcquireResult

```python
@dataclass
class AcquireResult:
    allowed: bool          # Whether request is allowed
    remaining: int         # Remaining requests in window
    limit: int             # Max requests allowed
    reset: float           # Unix timestamp when window resets
    retry_after: float     # Seconds to wait (0 if allowed)
```
