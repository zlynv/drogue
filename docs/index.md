---
description: Production-ready rate limiting and DDoS protection for Python web frameworks. FastAPI, Django, Flask support with Redis backend.
---

# drogue

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

## Quick start

### FastAPI

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

### Flask

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

### Django

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

## Example responses

### Successful request

```json
{
    "data": "value"
}
```

Headers:
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 9
X-RateLimit-Reset: 1690000060
```

### Rate limited (429)

```json
{
    "error": "Rate limit exceeded",
    "message": "Too many requests. Try again in 30 seconds.",
    "retry_after": 30,
    "limit": 10,
    "remaining": 0
}
```

Headers:
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1690000060
Retry-After: 30
```

### Banned (429)

```json
{
    "error": "Banned",
    "message": "You are banned due to repeated violations.",
    "retry_after": 300
}
```

---

## Features

| Category | What you get |
|----------|-------------|
| **Rate Limiting** | Token Bucket, Sliding Window, Fixed Window, cost-aware limits, blocking mode |
| **Identity** | IP-based, user-based, header-based, composite extractors |
| **Frameworks** | FastAPI (ASGI), Flask (decorator), Django (middleware), DRF (throttle) |
| **DDoS Detection** | Z-score anomaly detection, streaming Sentinel Model |
| **Auto-Ban** | Progressive ban with doubling duration |
| **Trust System** | State machine with fast path for verified users |
| **Circuit Breaker** | Closed/Open/HalfOpen states |
| **Probe Detection** | Sequential path detection, timing analysis |
| **CIDR Filtering** | Allow/block IP ranges |
| **Adaptive Limits** | CPU/memory-based scaling |
| **Defense Randomization** | Per-session variance, honeypots |
| **Probabilistic Storage** | Count-Min Sketch, Bloom Filter, HyperLogLog |
| **Observability** | Prometheus metrics, OpenTelemetry tracing |

---

## Install

```bash
pip install drogue

# With framework extras
pip install drogue[fastapi]
pip install drogue[django]
pip install drogue[flask]
pip install drogue[drf]
pip install drogue[redis]
pip install drogue[all]
```

---

## Links

- [Documentation](https://zlynv.github.io/drogue/)
- [GitHub](https://github.com/zlynv/drogue)
- [PyPI](https://pypi.org/project/drogue/)
