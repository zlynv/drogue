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
| `precision` | 14 | Bits of precision (higher = more accurate, more memory) |

---

## Integration with Rate Limiting

### Heavy Hitter Detection with Count-Min Sketch

```python
from drogue.storage.probabilistic import CountMinSketch
from drogue.adapters.fastapi import DrogueLimiter

cms = CountMinSketch(width=2**20, depth=4)
limiter = DrogueLimiter(app)

@app.middleware("http")
async def heavy_hitter_check(request: Request, call_next):
    client_ip = request.client.host
    cms.add(client_ip)
    
    # If a single client exceeds threshold
    if cms.estimate(client_ip) > 5000:
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded: heavy hitter detected"}
        )
    
    return await call_next(request)
```

### Bloom Filter for IP Allow/Deny Lists

```python
from drogue.storage.probabilistic import BloomFilter
from drogue.adapters.fastapi import DrogueLimiter

# Initialize from config
ip_allowlist = BloomFilter(capacity=1_000_000, false_positive_rate=0.001)
ip_denylist = BloomFilter(capacity=100_000, false_positive_rate=0.001)

for ip in config.ALLOWED_IPS:
    ip_allowlist.add(ip)
for ip in config.DENIED_IPS:
    ip_denylist.add(ip)

limiter = DrogueLimiter(app)

@app.middleware("http")
async def ip_filter(request: Request, call_next):
    client_ip = request.client.host
    
    # Check denylist first (fast path for known bad actors)
    if ip_denylist.check(request.client.host):
        return JSONResponse(status_code=403, content={"error": "IP denied"})
    
    # Check allowlist (if configured)
    if not ip_allowlist.check(request.client.host):
        return JSONResponse(status_code=403, content={"error": "IP not allowed"})
    
    return await call_next(request)
```

### Cuckoo Filter for Session Tracking

```python
from drogue.storage.probabilistic import CuckooFilter
from fastapi import FastAPI, Request, Response

sessions = CuckooFilter(capacity=1_000_000)

@app.post("/login")
async def login(credentials: Credentials):
    session_id = create_session_id()
    sessions.add(session_id)
    response = Response(content="Logged in")
    response.set_cookie("session_id", session_id)
    return response

@app.post("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and sessions.remove(session_id):
        return {"ok": True}
    return {"error": "Session not found"}

@app.middleware("http")
async def validate_session(request: Request, call_next):
    session_id = request.cookies.get("session_id")
    if session_id and not sessions.check(session_id):
        return JSONResponse(status_code=401, content={"error": "Invalid session"})
    return await call_next(request)
```

### HyperLogLog for Unique Visitor Metrics

```python
from drogue.storage.probabilistic import HyperLogLog
from drogue.adapters.fastapi import DrogueLimiter

visitor_hll = HyperLogLog(precision=14)
endpoint_hll = {}

@app.middleware("http")
async def track_visitors(request: Request, call_next):
    response = await call_next(request)
    
    path = request.url.path
    user_id = request.headers.get("X-User-ID", request.client.host)
    
    # Global unique visitors
    visitor_hll.add(user_id)
    
    # Per-endpoint unique visitors
    if path not in endpoint_hll:
        endpoint_hll[path] = HyperLogLog(precision=12)
    endpoint_hll[path].add(user_id)
    
    return response

@app.get("/metrics/visitors")
async def get_visitor_metrics():
    return {
        "total_unique_visitors": visitor_hll.count(),
        "per_endpoint": {
            path: hll.count() 
            for path, hll in endpoint_hll.items()
        }
    }
```

### Complete Protection Pipeline

```python
from drogue.adapters.fastapi import DrogueLimiter
from drogue.protection.pipeline import ProtectionPipeline
from drogue.protection.ddos import DDoSDetector
from drogue.protection.ban import ProgressiveBanManager
from drogue.storage.probabilistic import CountMinSketch, BloomFilter, CuckooFilter, HyperLogLog

# Probabilistic structures
cms = CountMinSketch(width=2**20, depth=4)
ip_allowlist = BloomFilter(capacity=1_000_000, false_positive_rate=0.001)
ip_denylist = BloomFilter(capacity=100_000, false_positive_rate=0.001)
sessions = CuckooFilter(capacity=1_000_000)
visitor_hll = HyperLogLog(precision=14)

# Standard protection
ddos = DDoSDetector(window=60.0, z_threshold=3.0, min_clients=10)
ban = ProgressiveBanManager(threshold=5, window=300.0)

pipeline = ProtectionPipeline(ddos=ddos, ban=ban)

app = FastAPI()
limiter = DrogueLimiter(app, pipeline=pipeline)

@app.middleware("http")
async def full_protection(request: Request, call_next):
    client_ip = request.client.host
    user_id = request.headers.get("X-User-ID", client_ip)
    
    # 1. IP deny list (fast, probabilistic)
    if ip_denylist.check(client_ip):
        return JSONResponse(status_code=403, content={"error": "IP denied"})
    
    # 2. Allow list
    if ip_allowlist.check(client_ip):
        return await call_next(request)
    
    # 3. Heavy hitter detection
    cms.add(user_id)
    if cms.estimate(user_id) > 5000:
        return JSONResponse(status_code=429, content={"error": "Heavy hitter detected"})
    
    # 4. Session validation
    session_id = request.cookies.get("session_id")
    if session_id and not sessions.check(session_id):
        return JSONResponse(status_code=401, content={"error": "Invalid session"})
    
    # 5. Track unique visitors
    visitor_hll.add(user_id)
    
    # 6. Standard protection pipeline
    result = await pipeline.check(key=user_id, context={"client": {"host": client_ip}})
    if not result.allowed:
        return JSONResponse(
            status_code=result.status_code,
            content={"error": result.reason, "retry_after": result.retry_after}
        )
    
    response = await call_next(request)
    return response
```

## Performance Comparison

| Structure | 1M Keys | Use Case |
|-----------|---------|----------|
| Redis Set | ~800 MB | Exact counts, sets |
| Count-Min Sketch | ~10 MB | Heavy hitters, frequency |
| Bloom Filter | ~1.2 MB | Allow/deny lists |
| Cuckoo Filter | ~1.5 MB | Sessions (supports delete) |
| HyperLogLog | ~12 KB | Unique visitor count |

## Best Practices

1. **Don't use for critical security** - Probabilistic structures can have false positives/negatives
2. **Layer with exact structures** - Use Redis for bans/sessions, probabilistic for analytics
3. **Tune parameters** - Adjust width/depth/error_rate based on your accuracy/memory needs
3. **Monitor false positives** - Track and adjust Bloom Filter false positive rate
4. **Combine with exact structures** - Use probabilistic for hot-path, exact for critical paths

## When NOT to Use

- Authentication/Authorization decisions (use exact structures)
- Financial transactions (need exact counts)
- Legal/compliance requirements (need exact audit trails)
- Small datasets (<10k items) where memory savings don't matter
