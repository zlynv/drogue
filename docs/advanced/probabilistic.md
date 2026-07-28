# Probabilistic Storage

## Overview

Probabilistic data structures provide memory-efficient alternatives to traditional storage for rate limiting and tracking.

## Count-Min Sketch

Approximate frequency counting with bounded error.

```python
from drogue.storage.probabilistic import CountMinSketch

cms = CountMinSketch(width=2**20, depth=4, error_rate=0.02)

# Add to count
cms.add("user123")
cms.add("user123")

# Estimate count (always >= actual count)
count = cms.estimate("user123")  # Returns approximately 2
```

**Properties:**

- Memory: 10MB for 1M keys
- Error: Plus/minus 2%
- Always overestimates, never underestimates
- Single-pass, O(1) per operation

## Bloom Filter

Set membership testing with false positives.

```python
from drogue.storage.probabilistic import BloomFilter

bf = BloomFilter(capacity=1_000_000, false_positive_rate=0.001)

bf.add("ip_address")

if bf.check("ip_address"):  # True = probably in set
    pass

if not bf.check("unknown"):  # False = definitely not in set
    pass
```

**Properties:**

- Memory: 1.2MB for 1M entries
- False positive rate: 0.1%
- No false negatives
- Cannot delete entries

## Cuckoo Filter

Like Bloom Filter but supports deletion.

```python
from drogue.storage.probabilistic import CuckooFilter

cf = CuckooFilter(capacity=1_000_000)

cf.add("session_id")

if cf.check("session_id"):  # True = probably in set
    pass

cf.remove("session_id")  # Supports deletion
```

**Properties:**

- Memory: Similar to Bloom Filter
- Supports deletion
- Higher overhead than Bloom Filter

## HyperLogLog

Unique visitor counting with minimal memory.

```python
from drogue.storage.probabilistic import HyperLogLog

hll = HyperLogLog(precision=14)

hll.add("user1")
hll.add("user2")
hll.add("user1")  # Duplicate, does not change count

count = hll.count()  # Returns approximately 2
```

**Properties:**

- Memory: 12KB per endpoint
- Error: Approximately 0.8%
- Cannot list elements
- Can merge multiple HyperLogLogs

## Comparison

| Structure | Memory (1M) | Error | Use Case |
|-----------|-------------|-------|----------|
| Count-Min Sketch | 10MB | ±2% | Rate limit counters |
| Bloom Filter | 1.2MB | 0.1% FP | IP blocklist |
| Cuckoo Filter | 1.2MB | 0.1% FP | Session dedup |
| HyperLogLog | 12KB | 0.8% | Unique visitors |

## Integration with drogue

```python
from drogue.storage.probabilistic import CountMinSketch

class ProbabilisticStorage:
    def __init__(self):
        self._counters = CountMinSketch(width=2**20, depth=4)

    def increment(self, key: str, amount: int = 1) -> int:
        self._counters.add(key, amount)
        return self._counters.estimate(key)

    def get_count(self, key: str) -> int:
        return self._counters.estimate(key)

# Use with drogue
storage = ProbabilisticStorage()
limiter = DrogueLimiter(app, storage=storage)
```
