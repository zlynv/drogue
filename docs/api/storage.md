# Storage API

## Probabilistic Data Structures

### CountMinSketch

```python
from drogue.storage.probabilistic import CountMinSketch

cms = CountMinSketch(width=2**20, depth=4, error_rate=0.02)

cms.add("user123", count=1)
count = cms.estimate("user123")
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `width` | `1048576` | Number of counters |
| `depth` | `4` | Number of hash functions |
| `error_rate` | `0.02` | Expected error rate |

### BloomFilter

```python
from drogue.storage.probabilistic import BloomFilter

bloom = BloomFilter(capacity=1000000, false_positive_rate=0.001)

bloom.add("item_123")
exists = bloom.check("item_123")  # True or False
```

### CuckooFilter

```python
from drogue.storage.probabilistic import CuckooFilter

cuckoo = CuckooFilter(capacity=1000000, fingerprint_size=4, bucket_size=4)

cuckoo.add("item_123")
exists = cuckoo.check("item_123")
removed = cuckoo.remove("item_123")  # supports deletion
```

### HyperLogLog

```python
from drogue.storage.probabilistic import HyperLogLog

hll = HyperLogLog(precision=14)

hll.add("user_123")
cardinality = hll.count()  # estimated unique count

# Merge two HyperLogLogs
hll2 = HyperLogLog(precision=14)
hll.merge(hll2)
```
