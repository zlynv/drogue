# Benchmarks

Performance benchmarks for drogue's rate limiting algorithms and DDoS protection.

## Prerequisites

```bash
pip install locust pytest-benchmark
pip install -e ".[fastapi]"
```

## Function-Level Benchmarks

These measure pure algorithm performance without HTTP overhead.

### Algorithm Latency

```bash
pytest benchmarks/test_algorithm_latency.py -v --benchmark-only
```

Measures `acquire()` call performance for each algorithm (10,000 calls per round, 10 rounds).

### Throughput Comparison

```bash
pytest benchmarks/test_algorithm_throughput.py -v --benchmark-only
```

Compares all 5 algorithms side-by-side with identical parameters.

### Memory Usage

```bash
pytest benchmarks/test_memory.py -v --benchmark-only
```

Measures memory per key for each algorithm with 100,000 unique keys.

## HTTP Load Tests

These measure real-world performance with FastAPI.

### Rate Limiting Benchmark

```bash
# Start the server
python -m uvicorn benchmarks.apps.fastapi_app:app --port 8000

# Run load test
locust -f benchmarks/locustfile.py --headless -u 100 -r 10 --run-time 60s -H http://localhost:8000
```

### DDoS Protection Benchmark

```bash
# Start the server with DDoS protection
python -m uvicorn benchmarks.apps.ddos_app:app --port 8000

# Run DDoS load test
locust -f benchmarks/ddos_locustfile.py --headless -u 100 -r 10 --run-time 60s -H http://localhost:8000
```

### Live Dashboard

Both apps expose a live stats dashboard:

```bash
# Rate limiting stats
open http://localhost:8000/stats/html

# DDoS protection stats
open http://localhost:8000/stats/html
```

## Results

### Function-Level (Windows, Python 3.13, MemoryStorage)

| Algorithm | Mean (ms) | ops/sec | Min | Max |
|-----------|-----------|---------|-----|-----|
| GCRA | 11.28 | 88.7 | 10.84 | 11.60 |
| Token Bucket | 11.85 | 84.4 | 11.34 | 12.58 |
| Leaky Bucket | 12.23 | 81.8 | 11.59 | 12.85 |
| Fixed Window | 12.48 | 80.1 | 12.00 | 13.15 |
| Sliding Window | 23.50 | 42.5 | 20.99 | 41.43 |

### HTTP Load Test (100 users, 60 seconds)

| Metric | Value |
|--------|-------|
| Total Requests | 2,731,058 |
| Requests/sec | 2,446.9 |
| Rate Limited (429) | 93.1% |
| p50 | 130ms |
| p95 | 350ms |
| p99 | 470ms |

### DDoS Protection (50 users, 20 seconds)

| Metric | Value |
|--------|-------|
| Total Requests | 42,815 |
| Requests/sec | 2,173.9 |
| Banned (403) | 97.8% |
| Rate Limited (429) | 0.02% |
| p50 | 5ms |
| p99 | 10ms |

## Interpreting Results

### Function-Level

- **ops/sec**: Higher is better. Shows how many acquire() calls per second.
- **p50/p95/p99**: Lower is better. Shows latency distribution.
- **Standard Deviation**: Lower is better. Shows consistency.

### HTTP Load Test

- **Requests/sec**: Higher is better. Shows throughput under load.
- **Response Time**: Lower is better. Shows latency under load.
- **Failure Rate**: 429s are expected at high concurrency — this is the rate limiter working correctly.

### DDoS Protection

- **Banned (403)**: Attackers identified and blocked.
- **Rate Limited (429)**: Requests exceeding rate limits.
- **p50 Response Time**: Protection overhead should be <10ms.

## Algorithm Comparison

| Algorithm | Best For | Burst Support | Thread Safe |
|-----------|----------|---------------|-------------|
| Token Bucket | APIs with occasional bursts | Yes | Yes (CAS) |
| Sliding Window | General-purpose, distributed | No | Yes |
| Fixed Window | Simple use cases, low memory | No | Yes |
| GCRA | Telecom-grade smooth traffic | Configurable | Yes (CAS) |
| Leaky Bucket | Constant-rate traffic | No | Yes (CAS) |
