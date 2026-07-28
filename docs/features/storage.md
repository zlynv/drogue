# Storage Backends

## MemoryStorage

Default storage backend. Thread-safe, in-process.

```python
from drogue.core.storage.memory import MemoryStorage

storage = MemoryStorage()
limiter = DrogueLimiter(app, storage=storage)
```

**Characteristics:**

- Latency: ~5 microseconds per operation
- Throughput: 741K requests per second
- Memory: 150 bytes per key
- Scope: Single process only

## RedisStorage

Distributed storage backend for multi-worker setups.

```python
from drogue.core.storage.redis import RedisStorage

storage = RedisStorage(url="redis://localhost:6379")
limiter = DrogueLimiter(app, storage=storage)
```

**Characteristics:**

- Latency: ~1ms per operation
- Throughput: 50K requests per second
- Memory: Shared across workers
- Scope: Multiple processes, multiple machines

## Count-Min Sketch

Probabilistic storage for memory-efficient rate limiting.

```python
from drogue.storage.probabilistic import CountMinSketch

cms = CountMinSketch(width=2**20, depth=4)
cms.add("user123")
count = cms.estimate("user123")
```

**Characteristics:**

- Memory: 10MB for 1M keys
- Error: Plus/minus 2%
- Scope: Single process
- Trade-off: Approximate counts, but 80x less memory than Redis

## Bloom Filter

Set membership testing with false positives.

```python
from drogue.storage.probabilistic import BloomFilter

bf = BloomFilter(capacity=1_000_000, false_positive_rate=0.001)
bf.add("ip_address")

if bf.check("ip_address"):  # True = probably in set
    pass
```

**Characteristics:**

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

**Characteristics:**

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

**Characteristics:**

- Memory: 12KB per endpoint
- Error: Approximately 0.8%
- Cannot list elements
- Can merge multiple HyperLogLogs

## Comparison

| Backend | Latency | Memory (1M keys) | Use Case |
|---------|---------|------------------|----------|
| Memory | ~5us | 140MB | Single worker |
| Redis | ~1ms | 800MB | Multi-worker |
| Count-Min Sketch | ~5us | 10MB | Memory-constrained |
| Bloom Filter | ~5us | 1.2MB | IP blocklist |
| Cuckoo Filter | ~5us | 1.2MB | Session dedup |
| HyperLogLog | ~5us | 12KB | Unique visitors |
