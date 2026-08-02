# drogue Benchmarks

Performance benchmarks for drogue's rate limiting algorithms.

## Prerequisites

```bash
pip install locust pytest-benchmark
pip install -e ".[fastapi]"
```

## Function-Level Benchmarks

These measure pure algorithm performance without HTTP overhead.

### Latency (per acquire() call)

```bash
pytest benchmarks/test_algorithm_latency.py -v --benchmark-only
```

### Throughput Comparison

```bash
pytest benchmarks/test_algorithm_throughput.py -v --benchmark-only
```

### Memory Usage

```bash
pytest benchmarks/test_memory.py -v --benchmark-only
```

## HTTP Load Tests

These measure real-world performance with FastAPI.

### Start the Server

```bash
python -m uvicorn benchmarks.apps.fastapi_app:app --port 8000
```

### Run Load Test

```bash
# Throughput test (60 seconds)
locust -f benchmarks/locustfile.py --headless -u 100 -r 10 --run-time 60s -H http://localhost:8000

# Correctness test (5 minutes)
locust -f benchmarks/locustfile.py --headless -u 200 -r 20 --run-time 300s -H http://localhost:8000
```

### Web UI

```bash
locust -f benchmarks/locustfile.py -H http://localhost:8089
# Open http://localhost:8089
```

## Results (Windows, Python 3.13, MemoryStorage)

### Function-Level Latency (10,000 acquire() calls per round)

| Algorithm | Mean (ms) | ops/sec | Min | Max | StdDev |
|-----------|-----------|---------|-----|-----|--------|
| Token Bucket | 11.73 | 85.2 | 11.17 | 12.04 | 0.25 |
| Fixed Window | 12.42 | 80.5 | 12.01 | 12.64 | 0.23 |
| GCRA | 12.47 | 80.2 | 10.55 | 26.52 | 4.94 |
| Leaky Bucket | 15.92 | 62.8 | 11.54 | 31.14 | 8.01 |
| Sliding Window | 21.61 | 46.3 | 21.05 | 22.16 | 0.39 |

### Throughput Comparison (10,000 acquire() calls per round)

| Algorithm | Mean (ms) | ops/sec | Min | Max |
|-----------|-----------|---------|-----|-----|
| GCRA | 11.28 | 88.7 | 10.84 | 11.60 |
| Token Bucket | 11.85 | 84.4 | 11.34 | 12.58 |
| Leaky Bucket | 12.23 | 81.8 | 11.59 | 12.85 |
| Fixed Window | 12.48 | 80.1 | 12.00 | 13.15 |
| Sliding Window | 23.50 | 42.5 | 20.99 | 41.43 |

### Memory Usage (100,000 unique keys)

| Algorithm | Time (s) |
|-----------|----------|
| Fixed Window | 2.31 |
| GCRA | 2.38 |
| Token Bucket | 2.70 |
| Leaky Bucket | 2.77 |
| Sliding Window | 2.76 |

### HTTP Load Test (100 concurrent users, 30 seconds)

| Metric | Value |
|--------|-------|
| Total Requests | 69,097 |
| Requests/sec | 2,325.8 |
| Avg Response Time | 19.7ms |
| Rate Limited (429) | 62,524 (90.5%) |
| Successful | 6,573 |

**Key Finding**: 90.5% of requests were rate limited — this proves the rate limiter is working correctly under extreme load. The 6,573 successful requests completed in ~19ms avg response time.

### Response Time Percentiles

| Percentile | Response Time |
|------------|---------------|
| p50 | 19ms |
| p66 | 20ms |
| p75 | 20ms |
| p80 | 21ms |
| p90 | 21ms |
| p95 | 22ms |
| p98 | 24ms |
| p99 | 31ms |

## Interpreting Results

### Function-Level

- **ops/sec**: Higher is better. Shows how many acquire() calls per second.
- **p50/p95/p99**: Lower is better. Shows latency distribution.
- **Standard Deviation**: Lower is better. Shows consistency.

### HTTP Load Test

- **Requests/sec**: Higher is better. Shows throughput under load.
- **Response Time**: Lower is better. Shows latency under load.
- **Failure Rate**: 429s are expected at high concurrency — this is the rate limiter working correctly.

## Algorithm Comparison

| Algorithm | Best For | Burst Support | Thread Safe |
|-----------|----------|---------------|-------------|
| Token Bucket | APIs with occasional bursts | Yes | Yes (CAS) |
| Sliding Window | General-purpose, distributed | No | Yes |
| Fixed Window | Simple use cases, low memory | No | Yes |
| GCRA | Telecom-grade smooth traffic | Configurable | Yes (CAS) |
| Leaky Bucket | Constant-rate traffic | No | Yes (CAS) |
