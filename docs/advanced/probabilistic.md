# Probabilistic Data Structures

## What are probabilistic data structures?

Probabilistic data structures use clever algorithms to estimate answers using much less memory than exact structures. They trade perfect accuracy for massive memory savings. For example, a Bloom Filter can check if an item exists in 1MB of memory, while an exact HashSet would need 80MB for the same data.

## When to use them

- **Rate limiting at scale**: Count-Min Sketch tracks millions of keys in MBs
- **IP blocklists**: Bloom Filter checks millions of IPs in KBs
- **Unique visitors**: HyperLogLog counts millions of unique users in 12KB
- **Session deduplication**: Cuckoo Filter checks and removes items efficiently

---

## Count-Min Sketch

### What it is

A Count-Min Sketch estimates the frequency of items in a stream. It uses multiple hash functions and a 2D array of counters. It can overestimate but never underestimate counts.

### How it works

```
1. Create a 2D array (width x depth) of counters, all zero
2. For each item:
   - Hash the item with each of the depth hash functions
   - Increment the counter at each (hash, depth) position
3. To estimate count:
   - Hash the item with each hash function
   - Return the minimum counter value
```

### Memory savings

| Items | Exact (dict) | Count-Min Sketch | Savings |
|-------|-------------|------------------|---------|
| 1M | 800 MB | 10 MB | 80x |
| 10M | 8 GB | 100 MB | 80x |
| 100M | 80 GB | 1 GB | 80x |

### Usage

```python
from drogue.storage.probabilistic import CountMinSketch

cms = CountMinSketch(width=2**20, depth=4, error_rate=0.02)

# Add items
cms.add("user123")
cms.add("user123")  # Count increases
cms.add("user456")

# Estimate count
count = cms.estimate("user123")  # 2 (accurate)
count = cms.estimate("user456")  # 1 (accurate)
count = cms.estimate("user789")  # 0 (not seen)
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `width` | 1048576 | Number of counters (power of 2) |
| `depth` | 4 | Number of hash functions |
| `error_rate` | 0.02 | Expected error rate (2%) |

---

## Bloom Filter

### What it is

A Bloom Filter checks if an item is "probably in the set" or "definitely not in the set". It uses multiple hash functions and a bit array. False positives are possible (says "yes" when item isn't there), but false negatives are impossible (says "no" means it's definitely not there).

### How it works

```
1. Create a bit array of size m, all zeros
2. For each item:
   - Hash the item with k hash functions
   - Set the bit at each hash position to 1
3. To check if item exists:
   - Hash the item with k hash functions
   - If ALL bits are 1, item "probably" exists
   - If ANY bit is 0, item "definitely" doesn't exist
```

### Usage

```python
from drogue.storage.probabilistic import BloomFilter

bloom = BloomFilter(capacity=1000000, false_positive_rate=0.001)

# Add items
bloom.add("user123")
bloom.add("ip:192.168.1.1")

# Check items
exists = bloom.check("user123")     # True (definitely in set)
exists = bloom.check("ip:10.0.0.1") # False (definitely not in set)
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `capacity` | 1000000 | Expected number of items |
| `false_positive_rate` | 0.001 | False positive rate (0.1%) |

---

## Cuckoo Filter

### What it is

A Cuckoo Filter is like a Bloom Filter but supports deletion. It can check, add, and remove items efficiently. It uses fingerprints (small hashes) and a cuckoo hashing scheme.

### How it works

```
1. Each item is hashed to get a fingerprint (small hash)
2. The fingerprint is stored in one of two possible buckets
3. To check: look in both buckets for the fingerprint
4. To add: store fingerprint in one bucket; if full, kick out existing item to its alternate bucket
5. To remove: find and delete the fingerprint from either bucket
```

### Usage

```python
from drogue.storage.probabilistic import CuckooFilter

cuckoo = CuckooFilter(capacity=1000000)

# Add items
added = cuckoo.add("session_abc")  # True
added = cuckoo.add("session_def")  # True

# Check items
exists = cuckoo.check("session_abc")  # True

# Remove items (Bloom Filter can't do this!)
removed = cuckoo.remove("session_abc")  # True
exists = cuckoo.check("session_abc")    # False
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `capacity` | 1000000 | Expected number of items |
| `fingerprint_size` | 4 | Size of fingerprint in bytes |
| `bucket_size` | 4 | Items per bucket |
| `max_kicks` | 500 | Max relocations per insert |

---

## HyperLogLog

### What it is

HyperLogLog estimates the number of unique items in a stream (cardinality). It uses the pattern of leading zeros in hashes to estimate how many unique items there are. It's remarkably accurate for its memory usage.

### How it works

```
1. Hash each item
2. Look at the leading zeros of the hash
3. The maximum number of leading zeros seen correlates to log2(unique count)
4. Use this to estimate cardinality
```

### Memory usage

| Precision | Memory | Standard Error |
|-----------|--------|----------------|
| 10 | 1 KB | ~3.3% |
| 12 | 4 KB | ~1.6% |
| 14 | 16 KB | ~0.8% |
| 16 | 64 KB | ~0.4% |

### Usage

```python
from drogue.storage.probabilistic import HyperLogLog

hll = HyperLogLog(precision=14)  # 16KB memory, 0.8% error

# Add items
for i in range(10000):
    hll.add(f"user_{i}")

# Count unique items
count = hll.count()  # ~9920 (within 0.8% of 10000)

# Merge two HyperLogLogs
hll2 = HyperLogLog(precision=14)
hll2.add("user_1")
hll2.add("user_2")
hll.merge(hll2)
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `precision` | 14 | Bits of precision (higher = more accurate, more memory) |
