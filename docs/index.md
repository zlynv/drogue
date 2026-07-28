# drogue

Drop-in replacement for slowapi with DDoS detection, WebSocket support, and 9x faster trusted-user paths.

## Install

```bash
pip install drogue

# With framework support
pip install drogue[fastapi]   # FastAPI + Starlette
pip install drogue[django]    # Django
pip install drogue[flask]     # Flask
pip install drogue[drf]       # Django REST Framework
pip install drogue[redis]     # Redis backend
pip install drogue[all]       # Everything
```

## Quick Start

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

No `request` parameter. No middleware setup. Works with Flask and Django too.

## Features

**Rate Limiting** -- Token Bucket (burst-friendly), Sliding Window (most accurate), Fixed Window (simplest), cost-aware limits, blocking mode

**Storage** -- In-memory (5us), Redis (distributed), Count-Min Sketch (10MB for 1M keys)

**Frameworks** -- FastAPI (pure ASGI middleware), Flask (decorator plus hook), Django (decorator plus middleware)

**Protection** -- DDoS detection (Z-score plus streaming), probe detection (early warning), progressive auto-ban (5 levels), circuit breaker, CIDR filtering, adaptive limits, shadow mode, trust caching, defense randomization, honeypots

**Observability** -- Prometheus metrics, OpenTelemetry tracing, structured logging

## Performance

| Metric | drogue | Context |
|--------|--------|---------|
| Trusted user | ~5us | LRU cache hit, skips algorithm evaluation |
| Standard user | ~43us | 7-23x faster than Redis round-trip |
| Throughput | 741K req/s | Token Bucket, single worker, in-memory |
| Memory per key | 150 bytes | vs 800 bytes in Redis |
| Count-Min Sketch | 10MB | Replaces 800MB Redis for 1M keys |

## Migrate from slowapi

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

## Known Limitations

- Ban state is in-memory only by default. Redis persistence planned for v0.3.
- Trust cache is per-process. Multi-worker setups need separate trust state per worker.
- Flask headers for dict-returning views do not inject automatically.

## License

MIT License -- Created by [Zlynv](https://github.com/Zlynv)
