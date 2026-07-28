# Storage

## MemoryStorage

The default backend. In-process, thread-safe, zero dependencies.

```python
from drogue.core.storage.memory import MemoryStorage
storage = MemoryStorage()
```

- Thread-safe via `RLock`
- Lazy TTL cleanup every 100 operations
- ~150 bytes per key
- Per-process only

## RedisStorage

Distributed backend for multi-process deployments.

```python
from drogue.core.storage.redis import RedisStorage
storage = RedisStorage(url="redis://localhost:6379")
```

Requires `pip install drogue[redis]`

- Atomic operations via Redis pipelines
- Lua scripts for compare-and-swap
- Key prefix namespace (default: `drogue:`)

## Probabilistic structures

| Structure | Memory (1M keys) | Error | Use case |
|-----------|-------------------|-------|----------|
| Count-Min Sketch | ~10 MB | +/- 2% | Rate limit counters |
| Bloom Filter | ~1.2 MB | 0.1% FP | IP blocklist |
| Cuckoo Filter | ~1.2 MB | 0.1% FP | Session dedup |
| HyperLogLog | ~12 KB | ~0.8% | Unique visitors |

```python
from drogue.storage.probabilistic import CountMinSketch

cms = CountMinSketch(width=2**20, depth=4)
cms.add("user123")
count = cms.estimate("user123")
```

## Choosing a backend

| Scenario | Backend |
|----------|---------|
| Development / testing | MemoryStorage |
| Single production server | MemoryStorage |
| Multiple workers | RedisStorage |
| Multiple servers | RedisStorage |
