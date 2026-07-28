# Storage API Reference

## Storage Interface

All storage backends implement the `Storage` abstract interface:

```python
from drogue.core.abstracts import Storage

class Storage(ABC):
    async def initialize(self) -> None: ...
    async def close(self) -> None: ...
    async def incr(self, key: str, window: float, amount: int = 1) -> int: ...
    async def get(self, key: str) -> Any: ...
    async def set(self, key: str, value: Any, ttl: float) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def expire(self, key: str, ttl: float) -> None: ...
    async def exists(self, key: str) -> bool: ...
    async def ttl(self, key: str) -> float: ...
    async def increment_by(self, key: str, amount: int, window: float) -> tuple[int, float]: ...
    async def compare_and_swap(self, key: str, expected: Any, new_value: Any, ttl: float) -> bool: ...
```

---

## MemoryStorage

In-memory storage for single-process deployments.

```python
from drogue.core.storage.memory import MemoryStorage

storage = MemoryStorage()
await storage.initialize()
```

**Characteristics:**

- Thread-safe via RLock
- Lazy TTL cleanup (every 100 ops)
- No persistence
- ~150 bytes per key

**Methods:**

All `Storage` interface methods, plus:

| Method | Description |
|--------|-------------|
| `__len__()` | Number of active keys |

---

## RedisStorage

Distributed storage for multi-process/multi-server deployments.

```python
from drogue.core.storage.redis import RedisStorage

storage = RedisStorage(
    url="redis://localhost:6379",
    prefix="drogue:",           # Key prefix namespace
)
await storage.initialize()
```

**Requirements:**

```bash
pip install "redis[hiredis]>=5.0.0"
```

**Characteristics:**

- Atomic operations via Redis pipelines
- Thread-safe and process-safe
- Lua scripts for compare-and-swap
- Key prefix namespacing

**Methods:**

All `Storage` interface methods, plus:

| Method | Description |
|--------|-------------|
| `eval_script(script, keys, args)` | Execute Lua script atomically |

**Key Prefix:**

All keys are prefixed with `drogue:` by default:

```
drogue:rate:user123
drogue:token:bucket:user123
drogue:fixed:window:user123
```

---

## Count-Min Sketch

Approximate frequency counting with bounded error.

```python
from drogue.storage.probabilistic import CountMinSketch

cms = CountMinSketch(
    width=2**20,      # Columns (higher = less error)
    depth=4,          # Hash functions (higher = less error)
    error_rate=0.02,  # Target error rate
)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `add(key, count=1)` | Add to count |
| `estimate(key)` | Estimate count (always >= actual) |
| `total_count` | Property: total count of all items |

**Memory:**

- ~10MB for 1M keys
- Error: ±2%

---

## Bloom Filter

Set membership testing with false positives.

```python
from drogue.storage.probabilistic import BloomFilter

bf = BloomFilter(
    capacity=1_000_000,
    false_positive_rate=0.001,
)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `add(key)` | Add element |
| `check(key)` | Check membership (True = probably in set) |
| `count` | Property: approximate count |

**Memory:**

- ~1.2MB for 1M entries
- False positive rate: 0.1%
- No false negatives
- Cannot delete entries

---

## Cuckoo Filter

Like Bloom Filter but supports deletion.

```python
from drogue.storage.probabilistic import CuckooFilter

cf = CuckooFilter(
    capacity=1_000_000,
    fingerprint_size=4,     # Bytes
    bucket_size=4,          # Entries per bucket
    max_kicks=500,          # Max displacement attempts
)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `add(key)` | Add element |
| `check(key)` | Check membership |
| `remove(key)` | Remove element (True if removed) |
| `count` | Property: approximate count |

**Memory:**

- ~1.2MB for 1M entries
- Supports deletion
- Higher overhead than Bloom Filter

---

## HyperLogLog

Unique visitor counting with minimal memory.

```python
from drogue.storage.probabilistic import HyperLogLog

hll = HyperLogLog(precision=14)  # 2^14 = 16384 registers
```

**Methods:**

| Method | Description |
|--------|-------------|
| `add(key)` | Add element |
| `count()` | Estimate cardinality |
| `merge(other)` | Merge another HyperLogLog |

**Memory:**

- ~12KB per endpoint
- Error: ~0.8%
- Cannot list elements
- Can merge multiple HyperLogLogs

---

## Comparison

| Backend | Memory (1M keys) | Persistence | Distributed | Use Case |
|---------|-------------------|-------------|-------------|----------|
| MemoryStorage | ~150 bytes/key | No | No | Dev/testing |
| RedisStorage | ~800MB | Yes | Yes | Production |
| Count-Min Sketch | ~10MB | No | No | Rate limit counters |
| Bloom Filter | ~1.2MB | No | No | IP blocklist |
| Cuckoo Filter | ~1.2MB | No | No | Session dedup |
| HyperLogLog | ~12KB | No | No | Unique visitors |

---

## Usage with drogue

```python
from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.storage.redis import RedisStorage

# Production with Redis
storage = RedisStorage(url="redis://localhost:6379")
limiter = DrogueLimiter(app, storage=storage)

# Development with memory
storage = MemoryStorage()
limiter = DrogueLimiter(app, storage=storage)

# High-volume with Count-Min Sketch
from drogue.storage.probabilistic import CountMinSketch
cms = CountMinSketch()
# Use as custom storage adapter
```
