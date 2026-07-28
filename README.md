# drogue

[![GitHub stars](https://img.shields.io/github/stars/zlynv/drogue?style=social)](https://github.com/zlynv/drogue)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-131%20passing-brightgreen.svg)](#development)
[![PyPI version](https://img.shields.io/pypi/v/drogue.svg)](https://pypi.org/project/drogue/)
[![PyPI downloads](https://img.shields.io/pypi/dm/drogue.svg)](https://pypi.org/project/drogue/)
[![Supported frameworks](https://img.shields.io/badge/frameworks-FastAPI%20%7C%20Django%20%7C%20Flask-lightgrey.svg)](#features)

Rate limiting and DDoS protection for Python web applications. Clean APIs, WebSocket support, and built-in defense layers.

**[Read the documentation](https://zlynv.github.io/drogue/)**

---

## What problem does drogue solve?

Web applications need rate limiting to prevent abuse, but existing solutions have gaps:

1. **Signature pollution** -- Most rate limiters force `request: Request` into every function signature, coupling your business logic to the rate limiter.

2. **No WebSocket protection** -- Real-time applications using WebSockets have no built-in rate limiting.

3. **No DDoS detection** -- Simple counters catch over-use, but cannot detect distributed attacks where each client stays below the limit.

4. **No trust differentiation** -- Every request goes through the same evaluation path, even for verified users.

drogue addresses all four. It rate-limits by identity (IP, user, header) without touching your function signatures, detects anomalous traffic patterns, and fast-tracks trusted clients.

---

## Who is drogue for?

- **API developers** who need rate limiting without framework lock-in
- **Teams running FastAPI, Django, or Flask** who want a single solution across all three
- **Platforms facing DDoS or abuse** that need more than simple request counting
- **Applications with WebSocket connections** that need real-time protection

---

## How it works

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter

app = FastAPI()
limiter = DrogueLimiter(app, default_limits=["100/minute"])

@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data():
    return {"data": "value"}
```

No `request: Request` parameter. Rate limit headers are injected automatically. The same pattern works for Flask and Django.

**Request flow:**

1. Client sends a request
2. drogue extracts the client key (IP, user ID, or custom header)
3. Rules are matched against the route
4. The algorithm evaluates the request (Token Bucket, Sliding Window, or Fixed Window)
5. Protection layers run (DDoS check, trust state, probe detection)
6. Response is returned with rate limit headers

---

## Features

| Category | What you get |
|----------|-------------|
| **Rate Limiting** | Token Bucket, Sliding Window, Fixed Window, cost-aware limits, blocking mode, burst control |
| **Identity** | IP-based, user-based, header-based, composite extractors, anti-spoof X-Forwarded-For |
| **Frameworks** | FastAPI (ASGI), Flask (decorator), Django (middleware + decorator), Django REST Framework (throttle) |
| **DDoS Detection** | Z-score anomaly detection, streaming Sentinel Model, probe pattern detection |
| **Auto-Ban** | Progressive ban with doubling duration (5m to 160m), configurable thresholds |
| **Trust System** | State machine (Unknown/Normal/Trusted/Distrusted/Banned), 9x throughput for verified users |
| **Circuit Breaker** | Closed/Open/HalfOpen states, automatic recovery |
| **Adaptive Limits** | CPU and memory-based scaling, reduces limits under system load |
| **Defense Randomization** | Per-session variance, honeypot paths, anti-fingerprinting |
| **CIDR Filtering** | Allow/block lists from config or files, IPv4 and IPv6 |
| **Probabilistic Storage** | Count-Min Sketch (10MB for 1M keys), Bloom Filter, Cuckoo Filter, HyperLogLog |
| **Observability** | Prometheus metrics, OpenTelemetry tracing, structured JSON logging |
| **Shadow Mode** | Test rules without enforcing, collect metrics before go-live |

---

## Performance

| Metric | drogue | Notes |
|--------|--------|-------|
| Trusted user | ~5us | LRU cache hit, skips algorithm evaluation |
| Standard user | ~43us | Full pipeline, in-memory storage |
| Throughput | 741K req/s | Token Bucket, single worker |
| Memory per key | 150 bytes | In-process storage |
| Count-Min Sketch | 10MB | Handles 1M keys |

*Measured on Intel i7-12700K, Python 3.12, asyncio single-worker, in-memory storage.*

---

## Install

```bash
pip install drogue

# With framework extras
pip install drogue[fastapi]   # FastAPI + Starlette
pip install drogue[django]    # Django
pip install drogue[flask]     # Flask
pip install drogue[drf]       # Django REST Framework
pip install drogue[redis]     # Redis backend
pip install drogue[all]       # Everything
```

---

## Quick Start

**FastAPI:**

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter

app = FastAPI()
limiter = DrogueLimiter(app, default_limits=["100/minute"])

@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data():
    return {"data": "value"}
```

**Flask:**

```python
from flask import Flask
from drogue.adapters.flask import DrogueLimiter

app = Flask(__name__)
limiter = DrogueLimiter(app, default_limits=["100/minute"])

@app.route("/api/data")
@limiter.limit("10/minute")
def get_data():
    return {"data": "value"}
```

**Django:**

```python
# settings.py
MIDDLEWARE = [
    "drogue.adapters.django.DrogueMiddleware",
]

# views.py
from drogue.adapters.django import DrogueRateLimiter
from django.http import JsonResponse

limiter = DrogueRateLimiter()

@limiter.limit("10/minute")
def get_data(request):
    return JsonResponse({"data": "value"})
```

---

## Migration from slowapi

```python
# Before (slowapi)
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data(request: Request):
    return {"data": "value"}

# After (drogue)
from drogue.adapters.fastapi import DrogueLimiter

limiter = DrogueLimiter(app)

@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data():
    return {"data": "value"}
```

---

## Known Limitations

- Ban state is in-memory only by default. Redis persistence planned for v0.3.
- Trust cache is per-process. Multi-worker setups need separate trust state per worker.
- Flask headers for dict-returning views do not inject automatically.

---

## Security

Report security vulnerabilities via GitHub's private vulnerability reporting. Do not open public issues for security bugs. Response time: 48 hours.

---

## Roadmap

- **v0.1** -- Core rate limiting, DDoS detection, three frameworks (current)
- **v0.2** -- Redis-backed ban state, WebSocket support for Django and Flask
- **v0.3** -- Trust cache cross-process sync, advanced Sentinel features
- **v1.0** -- Production-ready, full documentation site

---

## Development

```bash
pip install drogue[dev]
pytest
ruff check src/drogue/
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

Created by [Zlynv](https://github.com/Zlynv)
